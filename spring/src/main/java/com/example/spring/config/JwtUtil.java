package com.example.spring.config;

import io.jsonwebtoken.*;
import io.jsonwebtoken.security.Keys;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.stereotype.Component;

import javax.crypto.SecretKey;
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

    private final JwtProperties jwtProperties;

    /**
     * SecretKey 생성
     * Django와 동일한 SECRET_KEY 사용
     */
    private SecretKey getSigningKey() {
        byte[] keyBytes = jwtProperties.getSecretKey().getBytes(StandardCharsets.UTF_8);
        return Keys.hmacShaKeyFor(keyBytes);
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
                .signWith(getSigningKey())
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
                .signWith(getSigningKey())
                .compact();
    }

    /**
     * 토큰에서 Claims 추출
     */
    public Claims parseClaims(String token) {
        return Jwts.parser()
                .verifyWith(getSigningKey())
                .build()
                .parseSignedClaims(token)
                .getPayload();
    }

    /**
     * 토큰에서 사용자 ID 추출
     */
    public Long getBoothIdFromToken(String token) {
        Claims claims = parseClaims(token);
        Object boothIdObj = claims.get("booth_id");
        if (boothIdObj instanceof String) {
            return Long.valueOf((String) boothIdObj);
        } else if (boothIdObj instanceof Number) {
            return ((Number) boothIdObj).longValue();
        } else {
            throw new IllegalArgumentException("booth_id claim 타입 변환 실패: " + boothIdObj);
        }
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
        } catch (SecurityException e) {
            log.warn("JWT 서명이 유효하지 않습니다: {}", e.getMessage());
        } catch (IllegalArgumentException e) {
            log.warn("JWT 토큰이 비어있습니다: {}", e.getMessage());
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
