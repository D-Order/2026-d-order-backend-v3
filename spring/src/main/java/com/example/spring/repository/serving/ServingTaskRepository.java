package com.example.spring.repository.serving;

import com.example.spring.domain.serving.ServingStatus;
import com.example.spring.domain.serving.ServingTask;
import org.springframework.data.jpa.repository.JpaRepository;
import java.util.List;

public interface ServingTaskRepository extends JpaRepository<ServingTask, Long> {
    // 상태값(예: SERVE_REQUESTED)을 기준으로 서빙 대기 목록을 조회합니다.
    List<ServingTask> findAllByStatus(ServingStatus status);
}