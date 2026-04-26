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
    private Integer tableNumber;
    private String status;
    // 🌟 catchedBy 필드 삭제됨
    private LocalDateTime requestedAt;

    public static ServingTaskResponse from(ServingTask task) {
        return ServingTaskResponse.builder()
                .taskId(task.getId())
                .orderItemId(task.getOrderItemId())
                .tableNumber(task.getTableNumber())
                .status(task.getStatus() != null ? task.getStatus().name() : null)
                // 🌟 catchedBy 매핑 삭제됨
                .requestedAt(task.getRequestedAt())
                .build();
    }
}