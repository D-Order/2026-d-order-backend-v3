package com.example.spring.controller.auth;

import com.example.spring.config.CookieUtil;
import com.example.spring.dto.auth.request.LoginRequest;
import com.example.spring.service.auth.AuthService;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpServletResponse;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;



import java.util.Map;
import java.util.Collections;

import com.fasterxml.jackson.databind.ObjectMapper;


/**
 * 인증 관련 API 컨트롤러 (BFF 패턴)
 * Spring Boot → Django API 호출 → 토큰을 프론트엔드에 전달
 *
 * POST /api/v3/spring/auth - 로그인
 * DELETE /api/v3/spring/auth - 로그아웃
 * POST /api/v3/spring/auth/refresh - 토큰 재발급
 */
@RestController
// 앞에 "/api/v3/spring"은 nginx에서 프록시로 매핑되어 있으므로, 여기서는 "/auth"만 사용
@RequestMapping("/auth")
@RequiredArgsConstructor
@Slf4j
public class AuthController {

    private final AuthService authService;
    private final CookieUtil cookieUtil;
    private final ObjectMapper objectMapper = new ObjectMapper();

    /**
     * 로그인 (Django API 프록시)
     * POST /api/v3/spring/auth
     */
    @PostMapping
    public ResponseEntity<Map<String, Object>> login(@RequestBody LoginRequest request, HttpServletResponse response) {
        try {
            Map<String, Object> result = authService.login(request.getUsername(), request.getPassword(), response);
            return ResponseEntity.ok(result);
        } catch (AuthService.DjangoApiException e) {
            return handleDjangoError(e);
        }
    }

    /**
     * 로그아웃 (쿠키 직접 삭제)
     * DELETE /api/v3/spring/auth
     */
    @DeleteMapping
    public ResponseEntity<Map<String, Object>> logout(HttpServletResponse response) {
        cookieUtil.deleteJwtCookies(response);
        return ResponseEntity.ok(Collections.singletonMap("message", "로그아웃 성공"));
    }

    /**
     * JWT 토큰 재발급 (Django API 프록시)
     * POST /api/v3/spring/auth/refresh
     *
     * - Access 토큰 유효 → 그대로 반환 (200)
     * - Access 만료 + Refresh 유효 → 새 토큰 발급 (200)
     * - Refresh 만료 → 401 에러
     */
    @PostMapping("/refresh")
    public ResponseEntity<Map<String, Object>> refreshToken(HttpServletRequest request, HttpServletResponse response) {
        String accessToken = cookieUtil.getAccessTokenFromCookies(request.getCookies());
        String refreshToken = cookieUtil.getRefreshTokenFromCookies(request.getCookies());

        if (refreshToken == null) {
            return ResponseEntity.status(HttpStatus.UNAUTHORIZED).body(Collections.singletonMap("message", "Refresh 토큰 없음"));
        }

        try {
            Map<String, Object> result = authService.refreshToken(accessToken, refreshToken, response);
            return ResponseEntity.ok(result);
        } catch (AuthService.DjangoApiException e) {
            cookieUtil.deleteJwtCookies(response);
            return handleDjangoError(e);
        }
    }

    /**
     * Django API 에러를 파싱하여 프론트로 반환하는 공통 메서드
     */
    private ResponseEntity<Map<String, Object>> handleDjangoError(AuthService.DjangoApiException e) {
        try {
            // Django의 응답 body를 Map으로 변환
            Map<String, Object> errorBody = objectMapper.readValue(e.getResponseBody(), Map.class);
            return ResponseEntity.status(e.getStatus()).body(errorBody);
        } catch (Exception ex) {
            // JSON 파싱 실패 시 기본 응답
            return ResponseEntity.status(e.getStatus())
                    .body(Collections.singletonMap("message", "인증 처리 중 오류가 발생했습니다."));
        }
    }
}
