package com.example.spring.dto.staffcall.response;

import com.example.spring.domain.staffcall.StaffCall;
import com.fasterxml.jackson.annotation.JsonFormat;
import com.fasterxml.jackson.annotation.JsonProperty;
import lombok.Builder;
import lombok.Getter;

import java.time.LocalDateTime;

@Getter
@Builder
public class StaffCallItemResponse {

    @JsonProperty("staff_call_id")
    private Long staffCallId;

    @JsonProperty("table_id")
    private Long tableId;

    @JsonProperty("cart_id")
    private Long cartId;

    @JsonProperty("call_type")
    private String callType;

    /** SERVING | GENERAL */
    private String category;

    private String status;

    @JsonProperty("created_at")
    @JsonFormat(shape = JsonFormat.Shape.STRING, pattern = "yyyy-MM-dd'T'HH:mm:ss")
    private LocalDateTime createdAt;

    @JsonProperty("accepted_at")
    @JsonFormat(shape = JsonFormat.Shape.STRING, pattern = "yyyy-MM-dd'T'HH:mm:ss")
    private LocalDateTime acceptedAt;

    @JsonProperty("accepted_by")
    private String acceptedBy;

    @JsonProperty("completed_at")
    @JsonFormat(shape = JsonFormat.Shape.STRING, pattern = "yyyy-MM-dd'T'HH:mm:ss")
    private LocalDateTime completedAt;

    public static StaffCallItemResponse from(StaffCall sc) {
        return StaffCallItemResponse.builder()
                .staffCallId(sc.getId())
                .tableId(sc.getTableId())
                .cartId(sc.getCartId())
                .callType(sc.getCallType())
                .category(sc.getCategory() != null ? sc.getCategory().name() : null)
                .status(sc.getStatus() != null ? sc.getStatus().name() : null)
                .createdAt(sc.getCreatedAt())
                .acceptedAt(sc.getAcceptedAt())
                .acceptedBy(sc.getAcceptedBy())
                .completedAt(sc.getCompletedAt())
                .build();
    }
}
