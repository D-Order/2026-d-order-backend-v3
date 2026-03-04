package com.example.spring.service.auth;

import com.fasterxml.jackson.databind.ObjectMapper;
import jakarta.servlet.http.HttpServletResponse;
import lombok.Getter;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.http.*;
import org.springframework.stereotype.Service;
import org.springframework.web.client.HttpClientErrorException;
import org.springframework.web.client.RestTemplate;

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
private final ObjectMapper objectMapper;
    @Value("${django.api.base-url}")
    private String djangoApiBaseUrl;

    // Django API 에러를 담을 커스텀 예외 클래스
    @Getter
    public static class DjangoApiException extends RuntimeException {
        private final HttpStatus status;
        private final String responseBody;

        public DjangoApiException(HttpStatus status, String responseBody) {
            super("Django API Error: " + status);
            this.status = status;
            this.responseBody = responseBody;
        }
    }

    /**
     * CSRF 토큰 발급 (Django API 호출)
     * @return CSRF 토큰 정보 (csrfToken, csrfCookie)
     */
    private Map<String, String> getCsrfToken() {
        String url = djangoApiBaseUrl + "/api/v3/django/auth/csrf-token/";
        try {
            ResponseEntity<Map> response = restTemplate.exchange(url, HttpMethod.GET, null, Map.class);
            Map<String, String> result = new HashMap<>();
            Map body = response.getBody();
            if (body != null && body.get("csrfToken") != null) {
                result.put("csrfToken", body.get("csrfToken").toString());
            }
            List<String> cookies = response.getHeaders().get(HttpHeaders.SET_COOKIE);
            if (cookies != null) {
                for (String cookie : cookies) {
                    if (cookie.startsWith("csrftoken=")) {
                        result.put("csrfCookie", cookie.split(";")[0]);
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
     * @param username 사용자 아이디
     * @param password 비밀번호
     * @param response HttpServletResponse (쿠키 설정용)
     * @return Django 응답 데이터
     */
    public Map<String, Object> login(String username, String password, HttpServletResponse response) {
        String url = djangoApiBaseUrl + "/api/v3/django/auth/";
        Map<String, String> csrfData = getCsrfToken();
        Map<String, String> requestBody = new HashMap<>();
        requestBody.put("username", username);
        requestBody.put("password", password);

        String jsonBody;
        try {
            jsonBody = objectMapper.writeValueAsString(requestBody);
        } catch (Exception e) {
            throw new RuntimeException("JSON 변환 실패", e);
        }

        HttpHeaders headers = new HttpHeaders();
        headers.setContentType(MediaType.APPLICATION_JSON);
        if (csrfData.get("csrfToken") != null) headers.set("X-CSRFToken", csrfData.get("csrfToken"));
        if (csrfData.get("csrfCookie") != null) headers.set(HttpHeaders.COOKIE, csrfData.get("csrfCookie"));

        try {
            ResponseEntity<Map> djangoResponse = restTemplate.exchange(url, HttpMethod.POST, new HttpEntity<>(jsonBody, headers), Map.class);
            List<String> cookies = djangoResponse.getHeaders().get(HttpHeaders.SET_COOKIE);
            if (cookies != null) {
                for (String cookie : cookies) response.addHeader(HttpHeaders.SET_COOKIE, cookie);
            }
            return djangoResponse.getBody();
        } catch (HttpClientErrorException e) {
            // 커스텀 예외로 감싸서 전달
            throw new DjangoApiException(HttpStatus.valueOf(e.getStatusCode().value()), e.getResponseBodyAsString());
        }
    }

    /**
     * JWT 토큰 재발급 (Django API 호출)
     * - Access 토큰 유효 → 그대로 반환
     * - Access 만료 + Refresh 유효 → 새 토큰 발급
     * - Refresh 만료 → 401 에러
     * @param accessToken  현재 access_token (쿠키에서 추출)
     * @param refreshToken 현재 refresh_token (쿠키에서 추출)
     * @param response     HttpServletResponse (새 쿠키 설정용)
     * @return Django 응답 데이터
     */
    public Map<String, Object> refreshToken(String accessToken, String refreshToken, HttpServletResponse response) {
        String url = djangoApiBaseUrl + "/api/v3/django/auth/refresh/";
        Map<String, String> csrfData = getCsrfToken();

        HttpHeaders headers = new HttpHeaders();
        headers.setContentType(MediaType.APPLICATION_JSON);
        if (csrfData.get("csrfToken") != null) headers.set("X-CSRFToken", csrfData.get("csrfToken"));

        StringBuilder cookieHeader = new StringBuilder();
        if (csrfData.get("csrfCookie") != null) cookieHeader.append(csrfData.get("csrfCookie"));
        if (accessToken != null) cookieHeader.append("; access_token=").append(accessToken);
        if (refreshToken != null) cookieHeader.append("; refresh_token=").append(refreshToken);
        headers.set(HttpHeaders.COOKIE, cookieHeader.toString());

        try {
            ResponseEntity<Map> djangoResponse = restTemplate.exchange(url, HttpMethod.POST, new HttpEntity<>(headers), Map.class);
            List<String> cookies = djangoResponse.getHeaders().get(HttpHeaders.SET_COOKIE);
            if (cookies != null) {
                for (String cookie : cookies) response.addHeader(HttpHeaders.SET_COOKIE, cookie);
            }
            return djangoResponse.getBody();
        } catch (HttpClientErrorException e) {
            throw new DjangoApiException(HttpStatus.valueOf(e.getStatusCode().value()), e.getResponseBodyAsString());
        }
    }
}
