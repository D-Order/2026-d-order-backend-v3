package com.example.spring.config;

import org.springframework.http.*;
import org.springframework.web.client.RestTemplate;
import lombok.extern.slf4j.Slf4j;

import java.util.HashMap;
import java.util.List;
import java.util.Map;

@Slf4j
public class DjangoApiUtil {
    /**
     * CSRF 토큰 발급 (Django API 호출)
     * @param restTemplate RestTemplate 인스턴스
     * @param djangoApiBaseUrl Django API base url
     * @return CSRF 토큰 정보 (csrfToken, csrfCookie)
     */
    public static Map<String, String> getCsrfToken(RestTemplate restTemplate, String djangoApiBaseUrl) {
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
}
