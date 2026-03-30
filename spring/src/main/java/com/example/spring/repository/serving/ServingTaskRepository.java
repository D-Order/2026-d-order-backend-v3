package com.example.spring.repository.serving;

import com.example.spring.domain.serving.ServingStatus;
import com.example.spring.domain.serving.ServingTask;
import org.springframework.data.jpa.repository.JpaRepository;

import java.util.List;

public interface ServingTaskRepository extends JpaRepository<ServingTask, Long> {

    List<ServingTask> findAllByStatus(ServingStatus status);
}