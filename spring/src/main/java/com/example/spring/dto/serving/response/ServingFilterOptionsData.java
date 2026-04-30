package com.example.spring.dto.serving.response;

import lombok.AllArgsConstructor;
import lombok.Getter;

import java.util.List;

@Getter
@AllArgsConstructor
public class ServingFilterOptionsData {
    private List<ServingMenuFilterOption> menus;
    private List<Integer> tables;
}