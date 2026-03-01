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

    // Entity를 받아서 DTO로 변환하는 정적 팩토리 메서드
    public static ServingTaskResponse from(ServingTask task) {
        return ServingTaskResponse.builder()
                .taskId(task.getId())
                .orderItemId(task.getOrderItem().getId())
                .status(task.getStatus().name())
                .catchedBy(task.getCatchedBy())
                .requestedAt(task.getRequestedAt())
                .build();
    }
}