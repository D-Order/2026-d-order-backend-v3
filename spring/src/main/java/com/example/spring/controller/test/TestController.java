package com.example.spring.controller.test;

import com.example.spring.dto.test.request.TestCreateRequest;
import com.example.spring.dto.test.response.TestResponse;
import com.example.spring.service.test.TestService;
import lombok.RequiredArgsConstructor;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;
import com.example.spring.config.JwtUtil;
import com.example.spring.config.CookieUtil;

@RequiredArgsConstructor // Lombok 어노테이션
@RestController
public class TestController {
    private final TestService testService;
    private final JwtUtil jwtUtil;
    private final CookieUtil cookieUtil;

    @GetMapping("/check")
    public String home() {
        return "디오더 스부 서버가 정상적으로 실행중입니다.";
    }

    // 데이터 저장
    @PostMapping("/spring-test")
    public TestResponse saveTestData(@RequestBody TestCreateRequest request) {
        return testService.saveTestData(request);
    }

    // 저장된 데이터 조회 (ID로 조회)
    @GetMapping("/spring-test/{id}")
    public TestResponse getTestData(@PathVariable Long id) {
        return testService.getTestData(id);
    }

    // JWT 디코드 테스트 API
    @GetMapping("/spring-test/decode")
    public ResponseEntity<?> decodeJwt(jakarta.servlet.http.HttpServletRequest request) {
        String accessToken = cookieUtil.getAccessTokenFromCookies(request.getCookies());
        if (accessToken == null) {
            return ResponseEntity.status(401).body("access_token 쿠키 없음");
        }
        try {
            Long boothId = jwtUtil.getBoothIdFromToken(accessToken);
            return ResponseEntity.ok(java.util.Map.of(
                "booth_id", boothId
        
            ));
        } catch (Exception e) {
            return ResponseEntity.status(400).body("JWT 디코드 실패: " + e.getMessage());
        }
    }
}
