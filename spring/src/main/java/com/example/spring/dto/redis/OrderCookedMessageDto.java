package com.example.spring.dto.redis;

import com.fasterxml.jackson.annotation.JsonProperty;
import com.fasterxml.jackson.annotation.JsonAlias;
import lombok.AccessLevel;
import lombok.Getter;
import lombok.NoArgsConstructor;

import java.time.OffsetDateTime; // 🌟 수정됨

@Getter
@NoArgsConstructor(access = AccessLevel.PROTECTED)
public class OrderCookedMessageDto {

    @JsonProperty("order_item_id")
    private Long orderItemId;

    @JsonAlias({"table_num", "table_number"})
    private Integer tableNum;

    @JsonProperty("menu_id")
    private Long menuId;

    @JsonProperty("menu_name")
    private String menuName;

    @JsonProperty("quantity")
    private Integer quantity;

    private String status; // "cooked"

    // 🌟 수정됨: 강제 패턴을 지우고 OffsetDateTime을 사용해 Django 포맷을 그대로 흡수
    @JsonProperty("pushed_at")
    private OffsetDateTime pushedAt;
}