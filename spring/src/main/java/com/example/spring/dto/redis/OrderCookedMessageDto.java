package com.example.spring.dto.redis;

import com.fasterxml.jackson.annotation.JsonFormat;
import com.fasterxml.jackson.annotation.JsonProperty;
import lombok.AccessLevel;
import lombok.Getter;
import lombok.NoArgsConstructor;

import java.time.LocalDateTime;

@Getter
@NoArgsConstructor(access = AccessLevel.PROTECTED) // 역직렬화를 위해 기본 생성자 필요
public class OrderCookedMessageDto {

    @JsonProperty("order_item_id")
    private Long orderItemId;

    @JsonProperty("table_num")
    private Integer tableNum;

    @JsonProperty("menu_name")
    private String menuName;

    private Integer quantity;

    private String status; // "cooked"

    @JsonProperty("pushed_at")
    @JsonFormat(shape = JsonFormat.Shape.STRING, pattern = "yyyy-MM-dd'T'HH:mm:ss")
    private LocalDateTime pushedAt;
}