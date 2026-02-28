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

import java.util.HashMap;
import java.util.Map;

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

    /**
     * 로그인 (Django API 프록시)
     * POST /api/v3/spring/auth
     */
    @PostMapping
    public ResponseEntity<Map<String, Object>> login(
            @RequestBody LoginRequest request,
            HttpServletResponse response
    ) {
        try {
            // Django API 호출 → 응답의 Set-Cookie가 자동으로 response에 추가됨
            Map<String, Object> result = authService.login(
                    request.getUsername(),
                    request.getPassword(),
                    response
            );
            return ResponseEntity.ok(result);

        } catch (IllegalArgumentException e) {
            Map<String, Object> errorResponse = new HashMap<>();
            errorResponse.put("message", "로그인에 실패했습니다.");
            return ResponseEntity.badRequest().body(errorResponse);
        }
    }

    /**
     * 로그아웃 (쿠키 직접 삭제)
     * DELETE /api/v3/spring/auth
     */
    @DeleteMapping
    public ResponseEntity<Map<String, Object>> logout(HttpServletResponse response) {
        // 쿠키 삭제
        cookieUtil.deleteJwtCookies(response);

        Map<String, Object> responseBody = new HashMap<>();
        responseBody.put("message", "로그아웃 성공");
        return ResponseEntity.ok(responseBody);
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
    public ResponseEntity<Map<String, Object>> refreshToken(
            HttpServletRequest request,
            HttpServletResponse response
    ) {
        // 쿠키에서 토큰 추출
        String accessToken = cookieUtil.getAccessTokenFromCookies(request.getCookies());
        String refreshToken = cookieUtil.getRefreshTokenFromCookies(request.getCookies());

        // Refresh 토큰이 없으면 바로 401
        if (refreshToken == null) {
            Map<String, Object> errorResponse = new HashMap<>();
            errorResponse.put("message", "Refresh 토큰 없음");
            return ResponseEntity.status(HttpStatus.UNAUTHORIZED).body(errorResponse);
        }

        try {
            // Django API 호출
            Map<String, Object> result = authService.refreshToken(accessToken, refreshToken, response);
            return ResponseEntity.ok(result);

        } catch (AuthService.UnauthorizedException e) {
            // Refresh 토큰 만료 또는 유효하지 않음
            cookieUtil.deleteJwtCookies(response); // 쿠키 삭제
            
            Map<String, Object> errorResponse = new HashMap<>();
            errorResponse.put("message", "Refresh 토큰이 만료되었습니다. 다시 로그인해주세요.");
            return ResponseEntity.status(HttpStatus.UNAUTHORIZED).body(errorResponse);
        }
    }
}
