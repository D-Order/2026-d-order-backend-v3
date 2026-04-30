package com.example.spring.dto.serving.response;

import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Getter;

@Getter
@Builder
@AllArgsConstructor
public class ServingFilterOptionsResponse {
    private String message;
    private ServingFilterOptionsData data;
}