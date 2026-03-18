package com.example.spring.dto.table.request;

import lombok.Getter;
import lombok.NoArgsConstructor;
import java.util.List;

@Getter
@NoArgsConstructor
public class TableResetRequest {
    private List<Integer> table_nums;
}
