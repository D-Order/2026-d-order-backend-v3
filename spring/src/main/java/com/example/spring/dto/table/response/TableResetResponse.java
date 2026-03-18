package com.example.spring.dto.table.response;

import lombok.Getter;
import lombok.NoArgsConstructor;

@Getter
@NoArgsConstructor
public class TableResetResponse {
    private String message;
    private Data data;

    @Getter
    @NoArgsConstructor
    public static class Data {
        private int reset_table_cnt;
    }
}
