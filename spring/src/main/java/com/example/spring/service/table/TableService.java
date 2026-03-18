package com.example.spring.service.table;

// ...existing code...
import com.fasterxml.jackson.databind.ObjectMapper;
import com.example.spring.config.DjangoApiUtil;
import jakarta.servlet.http.HttpServletResponse;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.http.*;
import org.springframework.stereotype.Service;
import org.springframework.web.client.HttpClientErrorException;
import org.springframework.web.client.RestTemplate;

import java.util.List;
import java.util.Map;
import java.util.HashMap;

@Service
@RequiredArgsConstructor
@Slf4j
public class TableService {
    private final RestTemplate restTemplate;
    private final ObjectMapper objectMapper;
    @Value("${django.api.base-url}")
    private String djangoApiBaseUrl;

    // Django API 에러를 담을 커스텀 예외 클래스
    public static class DjangoApiException extends RuntimeException {
        private final HttpStatus status;
        private final String responseBody;

        public DjangoApiException(HttpStatus status, String responseBody) {
            super("Django API Error: " + status);
            this.status = status;
            this.responseBody = responseBody;
        }

        public HttpStatus getStatus() { return status; }
        public String getResponseBody() { return responseBody; }
    }

    // ...existing code...

    /**
     * 테이블 초기화 (Django API 호출)
     * @param tableNums 초기화할 테이블 번호 리스트
     * @param response HttpServletResponse (쿠키 설정용)
     * @return Django 응답 데이터
     */
    public Map<String, Object> resetTables(List<Integer> tableNums, HttpServletResponse response) {
        String url = djangoApiBaseUrl + "/api/v3/django/booth/tables/reset/";
        Map<String, String> csrfData = DjangoApiUtil.getCsrfToken(restTemplate, djangoApiBaseUrl);
        Map<String, Object> requestBody = new HashMap<>();
        requestBody.put("table_nums", tableNums);

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
            ResponseEntity<Map<String, Object>> djangoResponse = restTemplate.exchange(url, HttpMethod.POST, new HttpEntity<>(jsonBody, headers), (Class<Map<String, Object>>) (Class<?>) Map.class);
            List<String> cookies = djangoResponse.getHeaders().get(HttpHeaders.SET_COOKIE);
            if (cookies != null) {
                for (String cookie : cookies) response.addHeader(HttpHeaders.SET_COOKIE, cookie);
            }
            return djangoResponse.getBody(); // 타입 안전성 보장
        } catch (HttpClientErrorException e) {
            throw new DjangoApiException(HttpStatus.valueOf(e.getStatusCode().value()), e.getResponseBodyAsString());
        }
    }
}
