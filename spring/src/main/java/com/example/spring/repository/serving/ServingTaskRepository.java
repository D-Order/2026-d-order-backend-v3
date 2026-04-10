package com.example.spring.repository.serving;

import com.example.spring.domain.serving.ServingStatus;
import com.example.spring.domain.serving.ServingTask;
import org.springframework.data.jpa.repository.JpaRepository;

import java.util.List;

public interface ServingTaskRepository extends JpaRepository<ServingTask, Long> {

    /**
     * 운영자 인증으로 추출한 booth_id 기준으로
     * 해당 부스의 서빙 대기 목록만 조회
     */
    List<ServingTask> findByBoothIdAndStatusOrderByRequestedAtAsc(Long boothId, ServingStatus status);
}