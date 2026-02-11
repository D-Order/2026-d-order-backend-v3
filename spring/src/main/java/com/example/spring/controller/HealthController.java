package com.example.spring.controller;

import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RestController;

import javax.sql.DataSource;
import java.sql.Connection;
import java.util.Map;

/**
 * 헬스체크 컨트롤러
 * Docker/Nginx에서 서비스 상태 확인용
 * Django와 통일된 /health 엔드포인트 사용
 */
@RestController
public class HealthController {

    private final DataSource dataSource;

    public HealthController(DataSource dataSource) {
        this.dataSource = dataSource;
    }

    /**
     * 기본 헬스체크 - DB 연결 상태까지 확인
     * Nginx/Docker 헬스체크에서 사용
     */
    @GetMapping("/health")
    public ResponseEntity<Map<String, String>> healthCheck() {
        try {
            // DB 연결 확인
            try (Connection connection = dataSource.getConnection()) {
                if (connection.isValid(2)) {
                    return ResponseEntity.ok(Map.of("status", "ok"));
                }
            }
            return ResponseEntity.status(503).body(Map.of("status", "db_error"));
        } catch (Exception e) {
            return ResponseEntity.status(503).body(Map.of("status", "error"));
        }
    }
}
