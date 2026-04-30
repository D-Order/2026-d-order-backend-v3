package com.example.spring.dto.serving.django;

import com.fasterxml.jackson.annotation.JsonProperty;
import lombok.Getter;
import lombok.NoArgsConstructor;

@Getter
@NoArgsConstructor
public class DjangoBoothMypageResponse {
    private String message;
    private MypageData data;

    @Getter
    @NoArgsConstructor
    public static class MypageData {
        @JsonProperty("table_max_cnt")
        private Integer tableMaxCnt;
    }
}