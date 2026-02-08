package com.example.spring.service.test;

import com.example.spring.domain.test.Test;
import com.example.spring.dto.test.request.TestCreateRequest;
import com.example.spring.dto.test.response.TestResponse;
import com.example.spring.repository.test.TestRepository;
import lombok.RequiredArgsConstructor;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

@RequiredArgsConstructor // Lombok 어노테이션
@Service
public class TestService {

    private final TestRepository testRepository;

    // 저장 (POST)
    @Transactional
    public TestResponse saveTestData(TestCreateRequest request) {
        Test test = new Test(request.getName(), request.getDescription());
        Test savedTest = testRepository.save(test);
        return new TestResponse(savedTest);
    }

    // 조회 (GET)
    @Transactional(readOnly = true)
    public TestResponse getTestData(Long id) {
        Test test = testRepository.findById(id)
                .orElseThrow(() -> new IllegalArgumentException("해당 ID의 데이터가 없습니다. id=" + id));
        return new TestResponse(test);
    }
}
