package com.example.spring.controller.test;

import com.example.spring.dto.test.request.TestCreateRequest;
import com.example.spring.dto.test.response.TestResponse;
import com.example.spring.service.test.TestService;
import lombok.RequiredArgsConstructor;
import org.springframework.http.MediaType;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;

@RequiredArgsConstructor // Lombok 어노테이션
@RestController
public class TestController {
    private final TestService testService;


    @GetMapping("/")
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
}
