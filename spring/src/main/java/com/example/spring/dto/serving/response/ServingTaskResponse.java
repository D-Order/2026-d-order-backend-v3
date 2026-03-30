package com.example.spring.dto.serving.response;

import com.example.spring.domain.serving.ServingTask;
import lombok.Builder;
import lombok.Getter;

import java.time.LocalDateTime;

@Getter
@Builder
public class ServingTaskResponse {

    private Long taskId;
    private Long orderItemId;
    private String status;
    private String catchedBy;
    private LocalDateTime requestedAt;

    public static ServingTaskResponse from(ServingTask task) {
        return ServingTaskResponse.builder()
                .taskId(task.getId())
                .orderItemId(task.getOrderItemId())
                .status(task.getStatus() != null ? task.getStatus().name() : null)
                .catchedBy(task.getCatchedBy())
                .requestedAt(task.getRequestedAt())
                .build();
    }
}