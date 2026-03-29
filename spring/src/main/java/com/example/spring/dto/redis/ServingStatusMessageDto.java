package com.example.spring.dto.redis;

import com.fasterxml.jackson.annotation.JsonFormat;
import com.fasterxml.jackson.annotation.JsonInclude;
import com.fasterxml.jackson.annotation.JsonProperty;
import lombok.Builder;
import lombok.Getter;

import java.time.LocalDateTime;

@Getter
@Builder
// 필드 값이 null일 경우 JSON 변환 시 아예 제외시킵니다. (예: 서빙 완료 시 catched_by 불필요)
@JsonInclude(JsonInclude.Include.NON_NULL)
public class ServingStatusMessageDto {

    @JsonProperty("order_item_id")
    private Long orderItemId;

    private String status; // "serving", "served", "cooked"(취소 시)

    @JsonProperty("catched_by")
    private String catchedBy; // 서빙을 수락한 직원/로봇 ID

    @JsonProperty("pushed_at")
    @JsonFormat(shape = JsonFormat.Shape.STRING, pattern = "yyyy-MM-dd'T'HH:mm:ss")
    private LocalDateTime pushedAt;
}