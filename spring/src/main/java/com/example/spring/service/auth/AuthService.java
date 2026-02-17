package com.example.spring.service.auth;

import jakarta.servlet.http.HttpServletResponse;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.http.*;
import org.springframework.stereotype.Service;
import org.springframework.web.client.HttpClientErrorException;
import org.springframework.web.client.RestTemplate;
import com.fasterxml.jackson.databind.ObjectMapper;


import java.util.HashMap;
import java.util.List;
import java.util.Map;

/**
 * 인증 서비스 (BFF 패턴)
 * Spring Boot → Django API 호출 → 토큰을 프론트엔드에 전달
 */
@Service
@RequiredArgsConstructor
@Slf4j
public class AuthService {

    private final RestTemplate restTemplate;

    @Value("${django.api.base-url}")
    private String djangoApiBaseUrl;

    /**
     * CSRF 토큰 발급 (Django API 호출)
     *
     * @return CSRF 토큰 정보 (csrfToken, csrfCookie)
     */
    private Map<String, String> getCsrfToken() {
        String url = djangoApiBaseUrl + "/api/v3/django/auth/csrf-token/";

        try {
            ResponseEntity<Map> response = restTemplate.exchange(
                    url,
                    HttpMethod.GET,
                    null,
                    Map.class
            );

            Map<String, String> result = new HashMap<>();

            // 1. 응답 바디에서 csrfToken 추출
            Map body = response.getBody();
            if (body != null && body.get("csrfToken") != null) {
                result.put("csrfToken", body.get("csrfToken").toString());
            }

            // 2. Set-Cookie 헤더에서 csrftoken 쿠키 추출
            List<String> cookies = response.getHeaders().get(HttpHeaders.SET_COOKIE);
            if (cookies != null) {
                for (String cookie : cookies) {
                    if (cookie.startsWith("csrftoken=")) {
                        result.put("csrfCookie", cookie.split(";")[0]); // "csrftoken=xxx" 부분만
                    }
                }
            }

            return result;

        } catch (Exception e) {
            log.error("CSRF 토큰 발급 실패: {}", e.getMessage());
            return new HashMap<>();
        }
    }

    /**
     * 로그인 처리 (Django API 호출)
     *
     * @param username 사용자 아이디
     * @param password 비밀번호
     * @param response HttpServletResponse (쿠키 설정용)
     * @return Django 응답 데이터
     */
    public Map<String, Object> login(String username, String password, HttpServletResponse response) {
        String url = djangoApiBaseUrl + "/api/v3/django/auth/";

            // 1. CSRF 토큰 먼저 발급
            Map<String, String> csrfData = getCsrfToken();
            String csrfToken = csrfData.get("csrfToken");
            String csrfCookie = csrfData.get("csrfCookie");
        // 2. 요청 바디 생성 (JSON 문자열로 직접 변환)
        Map<String, String> requestBody = new HashMap<>();
        requestBody.put("username", username);
        requestBody.put("password", password);

        String jsonBody;
        try {
            jsonBody = new ObjectMapper().writeValueAsString(requestBody);
        } catch (Exception e) {
            throw new RuntimeException("JSON 변환 실패", e);
        }

        // 3. 헤더 설정 (CSRF 토큰 포함)
        HttpHeaders headers = new HttpHeaders();
        headers.setContentType(MediaType.APPLICATION_JSON);
        if (csrfToken != null) headers.set("X-CSRFToken", csrfToken);
        if (csrfCookie != null) headers.set(HttpHeaders.COOKIE, csrfCookie);

        log.info("[BFF-LOGIN] Spring → Django 로그인 요청: body={}, headers={}", jsonBody, headers);

        HttpEntity<String> entity = new HttpEntity<>(jsonBody, headers);

        try {
            // 4. Django API 호출
            ResponseEntity<Map> djangoResponse = restTemplate.exchange(
                    url,
                    HttpMethod.POST,
                    entity,
                    Map.class
            );

            // 5. Django Set-Cookie 헤더 → Spring 응답에 전달
            List<String> cookies = djangoResponse.getHeaders().get(HttpHeaders.SET_COOKIE);
            if (cookies != null) {
                for (String cookie : cookies) {
                    response.addHeader(HttpHeaders.SET_COOKIE, cookie);
                }
            }

            log.debug("[BFF-LOGIN] Django 응답: {}", djangoResponse);
            log.info("로그인 성공: {}", username);
            return djangoResponse.getBody();

        } catch (HttpClientErrorException e) {
            log.warn("로그인 실패: {} - {}", username, e.getMessage());
            log.warn("[BFF-LOGIN] 실패 응답 body: {}", e.getResponseBodyAsString());
            throw new IllegalArgumentException(e.getResponseBodyAsString());
        }
    }

    /**
     * JWT 토큰 재발급 (Django API 호출)
     * - Access 토큰 유효 → 그대로 반환
     * - Access 만료 + Refresh 유효 → 새 토큰 발급
     * - Refresh 만료 → 401 에러
     *
     * @param accessToken  현재 access_token (쿠키에서 추출)
     * @param refreshToken 현재 refresh_token (쿠키에서 추출)
     * @param response     HttpServletResponse (새 쿠키 설정용)
     * @return Django 응답 데이터
     */
    public Map<String, Object> refreshToken(String accessToken, String refreshToken, HttpServletResponse response) {
        String url = djangoApiBaseUrl + "/api/v3/django/auth/refresh/";

        // 1. CSRF 토큰 발급
        Map<String, String> csrfData = getCsrfToken();
        String csrfToken = csrfData.get("csrfToken");
        String csrfCookie = csrfData.get("csrfCookie");

        // 2. 헤더 설정 (CSRF + JWT 쿠키 포함)
        HttpHeaders headers = new HttpHeaders();
        headers.setContentType(MediaType.APPLICATION_JSON);

        if (csrfToken != null) {
            headers.set("X-CSRFToken", csrfToken);
        }

        // 쿠키 설정 (csrftoken + access_token + refresh_token)
        StringBuilder cookieHeader = new StringBuilder();
        if (csrfCookie != null) {
            cookieHeader.append(csrfCookie);
        }
        if (accessToken != null) {
            if (cookieHeader.length() > 0) cookieHeader.append("; ");
            cookieHeader.append("access_token=").append(accessToken);
        }
        if (refreshToken != null) {
            if (cookieHeader.length() > 0) cookieHeader.append("; ");
            cookieHeader.append("refresh_token=").append(refreshToken);
        }
        if (cookieHeader.length() > 0) {
            headers.set(HttpHeaders.COOKIE, cookieHeader.toString());
        }

        HttpEntity<Void> entity = new HttpEntity<>(headers);

        try {
            // 3. Django API 호출
            ResponseEntity<Map> djangoResponse = restTemplate.exchange(
                    url,
                    HttpMethod.POST,
                    entity,
                    Map.class
            );

            // 4. Django Set-Cookie 헤더 → Spring 응답에 전달 (새 토큰이 있을 경우)
            List<String> cookies = djangoResponse.getHeaders().get(HttpHeaders.SET_COOKIE);
            if (cookies != null) {
                for (String cookie : cookies) {
                    response.addHeader(HttpHeaders.SET_COOKIE, cookie);
                }
            }

            log.info("토큰 재발급/검증 성공");
            return djangoResponse.getBody();

        } catch (HttpClientErrorException e) {
            log.warn("토큰 재발급 실패: {}", e.getMessage());
            throw new UnauthorizedException(e.getResponseBodyAsString());
        }
    }

    /**
     * 인증 실패 예외
     */
    public static class UnauthorizedException extends RuntimeException {
        public UnauthorizedException(String message) {
            super(message);
        }
    }
}
