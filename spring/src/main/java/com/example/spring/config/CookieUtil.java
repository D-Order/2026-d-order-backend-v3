package com.example.spring.config;

import jakarta.servlet.http.Cookie;
import jakarta.servlet.http.HttpServletResponse;
import lombok.RequiredArgsConstructor;
import org.springframework.http.ResponseCookie;
import org.springframework.stereotype.Component;

/**
 * JWT 쿠키 설정/삭제 유틸리티
 * Django의 authentication/utils.py와 동일한 역할
 */
@Component
@RequiredArgsConstructor
public class CookieUtil {

    private final JwtProperties jwtProperties;

    /**
     * Access Token과 Refresh Token 쿠키 설정
     */
    public void setJwtCookies(HttpServletResponse response, String accessToken, String refreshToken) {
        // Access Token 쿠키
        ResponseCookie accessCookie = ResponseCookie.from(
                        jwtProperties.getCookie().getAccessTokenName(),
                        accessToken
                )
                .maxAge(jwtProperties.getAccessTokenExpiration() / 1000)
                .httpOnly(jwtProperties.getCookie().isHttpOnly())
                .sameSite(jwtProperties.getCookie().getSameSite())
                .secure(jwtProperties.getCookie().isSecure())
                .domain(jwtProperties.getCookie().getDomain())
                .path("/")
                .build();

        // Refresh Token 쿠키
        ResponseCookie refreshCookie = ResponseCookie.from(
                        jwtProperties.getCookie().getRefreshTokenName(),
                        refreshToken
                )
                .maxAge(jwtProperties.getRefreshTokenExpiration() / 1000)
                .httpOnly(jwtProperties.getCookie().isHttpOnly())
                .sameSite(jwtProperties.getCookie().getSameSite())
                .secure(jwtProperties.getCookie().isSecure())
                .domain(jwtProperties.getCookie().getDomain())
                .path("/")
                .build();

        response.addHeader("Set-Cookie", accessCookie.toString());
        response.addHeader("Set-Cookie", refreshCookie.toString());
    }

    /**
     * JWT 쿠키 삭제 (로그아웃)
     */
    public void deleteJwtCookies(HttpServletResponse response) {
        // Access Token 쿠키 삭제
        ResponseCookie accessCookie = ResponseCookie.from(
                        jwtProperties.getCookie().getAccessTokenName(),
                        ""
                )
                .maxAge(0)
                .httpOnly(jwtProperties.getCookie().isHttpOnly())
                .sameSite(jwtProperties.getCookie().getSameSite())
                .secure(jwtProperties.getCookie().isSecure())
                .domain(jwtProperties.getCookie().getDomain())
                .path("/")
                .build();

        // Refresh Token 쿠키 삭제
        ResponseCookie refreshCookie = ResponseCookie.from(
                        jwtProperties.getCookie().getRefreshTokenName(),
                        ""
                )
                .maxAge(0)
                .httpOnly(jwtProperties.getCookie().isHttpOnly())
                .sameSite(jwtProperties.getCookie().getSameSite())
                .secure(jwtProperties.getCookie().isSecure())
                .domain(jwtProperties.getCookie().getDomain())
                .path("/")
                .build();

        response.addHeader("Set-Cookie", accessCookie.toString());
        response.addHeader("Set-Cookie", refreshCookie.toString());
    }

    /**
     * 쿠키에서 Access Token 추출
     */
    public String getAccessTokenFromCookies(Cookie[] cookies) {
        return getTokenFromCookies(cookies, jwtProperties.getCookie().getAccessTokenName());
    }

    /**
     * 쿠키에서 Refresh Token 추출
     */
    public String getRefreshTokenFromCookies(Cookie[] cookies) {
        return getTokenFromCookies(cookies, jwtProperties.getCookie().getRefreshTokenName());
    }

    private String getTokenFromCookies(Cookie[] cookies, String cookieName) {
        if (cookies == null) return null;

        for (Cookie cookie : cookies) {
            if (cookieName.equals(cookie.getName())) {
                return cookie.getValue();
            }
        }
        return null;
    }
}
