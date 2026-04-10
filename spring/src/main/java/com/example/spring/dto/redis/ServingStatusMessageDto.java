package com.example.spring.dto.redis;

import com.fasterxml.jackson.annotation.JsonInclude;
import com.fasterxml.jackson.annotation.JsonProperty;
import lombok.Builder;
import lombok.Getter;

import java.time.OffsetDateTime; // 🌟 수정됨

@Getter
@Builder
@JsonInclude(JsonInclude.Include.NON_NULL)
public class ServingStatusMessageDto {

    @JsonProperty("order_item_id")
    private Long orderItemId;

    private String status; // "serving", "served", "cooked"(취소 시)


    // 🌟 수정됨: 타임존 지원을 위해 OffsetDateTime 사용
    @JsonProperty("pushed_at")
    private OffsetDateTime pushedAt;
}