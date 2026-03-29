package com.example.spring.controller.table;

import com.example.spring.config.CookieUtil;
import com.example.spring.dto.table.request.TableResetRequest;
import com.example.spring.service.table.TableService;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpServletResponse;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;

import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;

import java.util.Map;
import java.util.Collections;
import com.fasterxml.jackson.databind.ObjectMapper;

/**
 * 테이블 초기화 API 컨트롤러 (BFF)
 * Spring Boot → Django API 호출 → 응답을 프론트엔드에 전달
 * POST /api/v3/spring/table/reset
 */
@RestController
@RequestMapping("/table")
@RequiredArgsConstructor
@Slf4j
public class TableController {

    private final TableService tableService;
    private final CookieUtil cookieUtil;
    private final ObjectMapper objectMapper = new ObjectMapper();

    /**
     * 테이블 초기화 (Django API 프록시)
     * POST /api/v3/spring/table/reset
     */
    @PostMapping("/reset")
    public ResponseEntity<Map<String, Object>> resetTables(@RequestBody TableResetRequest request, HttpServletRequest httpRequest, HttpServletResponse response) {
        String accessToken = cookieUtil.getAccessTokenFromCookies(httpRequest.getCookies());
        String refreshToken = cookieUtil.getRefreshTokenFromCookies(httpRequest.getCookies());
        try {
            Map<String, Object> result = tableService.resetTables(request.getTable_nums(), accessToken, refreshToken, response);
            return ResponseEntity.ok(result);
        } catch (TableService.DjangoApiException e) {
            return handleDjangoError(e);
        }
    }

    /**
     * Django API 에러를 파싱하여 프론트로 반환하는 공통 메서드
     */
    private ResponseEntity<Map<String, Object>> handleDjangoError(TableService.DjangoApiException e) {
        try {
            Map<String, Object> errorBody = objectMapper.readValue(e.getResponseBody(), (Class<Map<String, Object>>) (Class<?>) Map.class);
            return ResponseEntity.status(e.getStatus()).body(errorBody);
        } catch (Exception ex) {
            return ResponseEntity.status(e.getStatus())
                    .body(Collections.singletonMap("message", "테이블 초기화 처리 중 오류가 발생했습니다."));
        }
    }
}
