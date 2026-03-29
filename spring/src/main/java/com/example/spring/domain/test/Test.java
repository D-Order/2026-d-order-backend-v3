package com.example.spring.domain.test;

import jakarta.persistence.*;
import lombok.AccessLevel;
import lombok.Getter;
import lombok.NoArgsConstructor;

@Getter // Lombok 어노테이션
@NoArgsConstructor(access = AccessLevel.PROTECTED) // Lombok 어노테이션
@Entity
@Table(name = "spring_test") // 테이블 명시 (선택사항이나 권장)
public class Test {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id = null;

    @Column(nullable = false)
    private String name;

    @Column(nullable = false)
    private String description; // 설명 필드 추가


    public Test(String name, String description) {
        this.name = name;
        this.description = description;
    }
}
