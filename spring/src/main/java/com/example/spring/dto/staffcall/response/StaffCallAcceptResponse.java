package com.example.spring.dto.staffcall.response;

import com.fasterxml.jackson.annotation.JsonFormat;
import com.fasterxml.jackson.annotation.JsonProperty;
import lombok.Builder;
import lombok.Getter;

import java.time.LocalDateTime;

@Getter
@Builder
public class StaffCallAcceptResponse {

    @JsonProperty("table_id")
    private Long tableId;

    @JsonProperty("cart_id")
    private Long cartId;

    @JsonProperty("call_type")
    private String callType;

    private String status;

    @JsonProperty("accepted_at")
    @JsonFormat(shape = JsonFormat.Shape.STRING, pattern = "yyyy-MM-dd'T'HH:mm:ss")
    private LocalDateTime acceptedAt;

    @JsonProperty("accepted_by")
    private String acceptedBy;
}
