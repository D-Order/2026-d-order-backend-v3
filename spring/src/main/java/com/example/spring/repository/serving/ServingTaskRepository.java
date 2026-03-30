package com.example.spring.repository.serving;

import com.example.spring.domain.serving.ServingStatus;
import com.example.spring.domain.serving.ServingTask;
import org.springframework.data.jpa.repository.JpaRepository;

import java.util.List;

public interface ServingTaskRepository extends JpaRepository<ServingTask, Long> {

    /**
     * Django의 orderitem 테이블과 조인하지 않고
     * serving_task 자체만 조회합니다.
     */
    List<ServingTask> findByStatusOrderByRequestedAtAsc(ServingStatus status);
}