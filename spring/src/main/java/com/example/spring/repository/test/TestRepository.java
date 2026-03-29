package com.example.spring.repository.test;


import com.example.spring.domain.test.Test;
import org.springframework.data.jpa.repository.JpaRepository;

public interface TestRepository  extends JpaRepository<Test, Long> {
}
