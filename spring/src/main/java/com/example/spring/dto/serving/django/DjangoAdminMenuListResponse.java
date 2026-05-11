package com.example.spring.dto.serving.django;

import com.fasterxml.jackson.annotation.JsonProperty;
import lombok.Getter;
import lombok.NoArgsConstructor;

import java.util.List;

@Getter
@NoArgsConstructor
public class DjangoAdminMenuListResponse {
    private String message;

    @JsonProperty("booth_id")
    private Long boothId;

    private List<MenuItem> data;

    @Getter
    @NoArgsConstructor
    public static class MenuItem {
        private Long id;
        private String name;
        private String category;

        @JsonProperty("is_soldout")
        private Boolean isSoldout;

        @JsonProperty("is_fixed")
        private Boolean isFixed;

        @JsonProperty("set_items")
        private List<SetItem> setItems;
    }

    @Getter
    @NoArgsConstructor
    public static class SetItem {
        @JsonProperty("menu_id")
        private Long menuId;
        private Integer quantity;

        @JsonProperty("base_price")
        private Integer basePrice;
        private Integer stock;
    }
}