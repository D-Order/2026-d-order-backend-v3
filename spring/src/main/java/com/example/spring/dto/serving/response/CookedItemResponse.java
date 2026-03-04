package com.example.spring.dto.serving.response;

import com.example.spring.domain.serving.ServingTask;
import lombok.Builder;
import lombok.Getter;

import java.time.LocalDateTime;

@Getter
@Builder
public class CookedItemResponse {

    private Long taskId;
    private Long orderItemId;

    // OrderItem 내부에 조인된 정보를 통해 메뉴 이름, 테이블 번호 등을 가져와 매핑할 수 있습니다.
    // private String menuName;
    // private Integer quantity;

    private String status;
    private LocalDateTime requestedAt;

    public static CookedItemResponse from(ServingTask task) {
        return CookedItemResponse.builder()
                .taskId(task.getId())
                .orderItemId(task.getOrderItem().getId())
                .status(task.getStatus().name())
                .requestedAt(task.getRequestedAt())
                .build();
    }
}