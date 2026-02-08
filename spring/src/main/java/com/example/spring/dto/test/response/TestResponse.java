package com.example.spring.dto.test.response;
import com.example.spring.domain.test.Test;
import lombok.Getter;

@Getter
public class TestResponse {
    private Long id;
    private String name;
    private String description;

    // Entity를 받아서 DTO로 변환하는 생성자
    public TestResponse(Test test) {
        this.id = test.getId();
        this.name = test.getName();
        this.description = test.getDescription();
    }
}
