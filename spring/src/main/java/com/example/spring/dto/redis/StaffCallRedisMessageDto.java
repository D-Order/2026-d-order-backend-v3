package com.example.spring.dto.redis;

import com.fasterxml.jackson.annotation.JsonFormat;
import com.fasterxml.jackson.annotation.JsonInclude;
import com.fasterxml.jackson.annotation.JsonProperty;
import lombok.Builder;
import lombok.Getter;

import java.time.LocalDateTime;

/**
 * Redis 발행용 — category 로 serving / general 구분
 */
@Getter
@Builder
@JsonInclude(JsonInclude.Include.NON_NULL)
public class StaffCallRedisMessageDto {

    private String event;

    @JsonProperty("staff_call_id")
    private Long staffCallId;

    @JsonProperty("booth_id")
    private Long boothId;

    @JsonProperty("table_id")
    private Long tableId;

    @JsonProperty("cart_id")
    private Long cartId;

    @JsonProperty("table_usage_id")
    private Long tableUsageId;

    @JsonProperty("table_num")
    private Integer tableNum;

    @JsonProperty("cart_price")
    private Integer cartPrice;

    @JsonProperty("call_type")
    private String callType;

    /** SERVING | GENERAL */
    private String category;

    private String status;

    @JsonProperty("pushed_at")
    @JsonFormat(shape = JsonFormat.Shape.STRING, pattern = "yyyy-MM-dd'T'HH:mm:ss")
    private LocalDateTime pushedAt;
}
