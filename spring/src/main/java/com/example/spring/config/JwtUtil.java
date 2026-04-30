package com.example.spring.config;

import io.jsonwebtoken.*;
import io.jsonwebtoken.security.Keys;
import io.jsonwebtoken.security.MacAlgorithm;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.stereotype.Component;

import javax.crypto.SecretKey;
import javax.crypto.spec.SecretKeySpec;
import java.lang.reflect.Constructor;
import java.nio.charset.StandardCharsets;
import java.util.Date;

/**
 * JWT 토큰 생성 및 검증 유틸리티
 * Django SimpleJWT와 호환되도록 구현
 */
@Component
@RequiredArgsConstructor
@Slf4j
public class JwtUtil {

    private static final int STRONG_SECRET_MIN_BYTES = 32;

    /**
     * jjwt 기본 HS256은 키를 256비트 이상만 허용한다. Django/PyJWT는 더 짧은 SECRET_KEY도 허용하므로,
     * 동일 alg id(HS256)로 최소 길이만 낮춘 MacAlgorithm을 jjwt-impl에서 리플렉션으로 만든다.
     */
    private static final String DEFAULT_MAC_ALGORITHM_CLASS = "io.jsonwebtoken.impl.security.DefaultMacAlgorithm";

    private final JwtProperties jwtProperties;

    private volatile MacAlgorithm relaxedHs256;

    private byte[] secretKeyUtf8Bytes() {
        return jwtProperties.getSecretKey().getBytes(StandardCharsets.UTF_8);
    }

    private boolean usesShortSecret() {
        return secretKeyUtf8Bytes().length < STRONG_SECRET_MIN_BYTES;
    }

    private MacAlgorithm hs256Algorithm() {
        if (!usesShortSecret()) {
            return Jwts.SIG.HS256;
        }
        if (relaxedHs256 == null) {
            synchronized (this) {
                if (relaxedHs256 == null) {
                    relaxedHs256 = createRelaxedHs256MacAlgorithm();
                }
            }
        }
        return relaxedHs256;
    }

    private static MacAlgorithm createRelaxedHs256MacAlgorithm() {
        try {
            Class<?> clazz = Class.forName(DEFAULT_MAC_ALGORITHM_CLASS);
            Constructor<?> ctor = clazz.getDeclaredConstructor(String.class, String.class, int.class);
            ctor.setAccessible(true);
            return (MacAlgorithm) ctor.newInstance("HS256", "HmacSHA256", 8);
        } catch (Exception e) {
            throw new IllegalStateException(
                    "짧은 SECRET_KEY용 HS256 MacAlgorithm을 만들 수 없습니다. jjwt-impl 버전을 확인하세요.", e);
        }
    }

    /**
     * SecretKey 생성 — Django SimpleJWT / PyJWT와 동일한 바이트열로 HMAC.
     * jjwt 0.12의 {@link Keys#hmacShaKeyFor}는 256비트 미만 키를 거부하므로, 짧을 때는 {@link SecretKeySpec}을 쓴다.
     */
    private SecretKey getSigningKey() {
        byte[] keyBytes = secretKeyUtf8Bytes();
        if (keyBytes.length >= STRONG_SECRET_MIN_BYTES) {
            return Keys.hmacShaKeyFor(keyBytes);
        }
        return new SecretKeySpec(keyBytes, "HmacSHA256");
    }

    /**
     * Access Token 생성
     */
    public String generateAccessToken(Long boothId, String username) {
        Date now = new Date();
        Date expiry = new Date(now.getTime() + jwtProperties.getAccessTokenExpiration());

        return Jwts.builder()
                .subject(String.valueOf(boothId))
                .claim("booth_id", boothId)
                .claim("username", username)
                .claim("token_type", "access")
                .issuedAt(now)
                .expiration(expiry)
                .signWith(getSigningKey(), hs256Algorithm())
                .compact();
    }

    /**
     * Refresh Token 생성
     */
    public String generateRefreshToken(Long boothId, String username) {
        Date now = new Date();
        Date expiry = new Date(now.getTime() + jwtProperties.getRefreshTokenExpiration());

        return Jwts.builder()
                .subject(String.valueOf(boothId))
                .claim("booth_id", boothId)
                .claim("username", username)
                .claim("token_type", "refresh")
                .issuedAt(now)
                .expiration(expiry)
                .signWith(getSigningKey(), hs256Algorithm())
                .compact();
    }

    /**
     * 토큰에서 Claims 추출
     */
    public Claims parseClaims(String token) {
        JwtParserBuilder builder = Jwts.parser().verifyWith(getSigningKey());
        if (usesShortSecret()) {
            builder = builder.sig().remove(Jwts.SIG.HS256).add(hs256Algorithm()).and();
        }
        return builder.build()
                .parseSignedClaims(token)
                .getPayload();
    }

    /**
     * 토큰에서 사용자 ID 추출
     */
    public Long getBoothIdFromToken(String token) {
        Claims claims = parseClaims(token);
        // Django SimpleJWT 기본 클레임은 user_id — 이 프로젝트는 Booth.pk == User.pk 이므로 동일
        Object boothIdObj = claims.get("booth_id");
        if (boothIdObj == null) {
            boothIdObj = claims.get("user_id");
        }
        if (boothIdObj instanceof String) {
            return Long.valueOf((String) boothIdObj);
        } else if (boothIdObj instanceof Number) {
            return ((Number) boothIdObj).longValue();
        } else {
            throw new IllegalArgumentException("booth_id/user_id claim 없음 또는 타입 변환 실패: " + boothIdObj);
        }
    }

    /**
     * SimpleJWT 호환 username 클레임 (직원 호출 수락 시 accepted_by 등)
     */
    public String getUsernameFromToken(String token) {
        Claims claims = parseClaims(token);
        Object username = claims.get("username");
        return username != null ? username.toString() : null;
    }

    /**
     * Django session_id custom claim 추출 (UUID 문자열, 없으면 null)
     */
    public String getSessionIdFromToken(String token) {
        Claims claims = parseClaims(token);
        Object sessionId = claims.get("session_id");
        return sessionId != null ? sessionId.toString() : null;
    }

    /**
     * 토큰 유효성 검증
     */
    public boolean validateToken(String token) {
        try {
            parseClaims(token);
            return true;
        } catch (ExpiredJwtException e) {
            log.warn("JWT 토큰이 만료되었습니다: {}", e.getMessage());
        } catch (UnsupportedJwtException e) {
            log.warn("지원하지 않는 JWT 토큰입니다: {}", e.getMessage());
        } catch (MalformedJwtException e) {
            log.warn("잘못된 JWT 토큰입니다: {}", e.getMessage());
        } catch (io.jsonwebtoken.security.SignatureException e) {
            log.warn("JWT 서명이 유효하지 않습니다: {}", e.getMessage());
        } catch (SecurityException e) {
            log.warn("JWT 서명이 유효하지 않습니다: {}", e.getMessage());
        } catch (IllegalArgumentException e) {
            log.warn("JWT 토큰이 비어있습니다: {}", e.getMessage());
        } catch (io.jsonwebtoken.security.WeakKeyException e) {
            log.warn("JWT 키 길이 검증 실패: {}", e.getMessage());
        }
        return false;
    }

    /**
     * Access Token 만료 시간 (초)
     */
    public int getAccessTokenExpirationSeconds() {
        return (int) (jwtProperties.getAccessTokenExpiration() / 1000);
    }

    /**
     * Refresh Token 만료 시간 (초)
     */
    public int getRefreshTokenExpirationSeconds() {
        return (int) (jwtProperties.getRefreshTokenExpiration() / 1000);
    }
}
