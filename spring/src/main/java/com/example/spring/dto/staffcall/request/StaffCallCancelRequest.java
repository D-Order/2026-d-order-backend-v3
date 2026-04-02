package com.example.spring.dto.staffcall.request;

import lombok.Getter;
import lombok.NoArgsConstructor;

@Getter
@NoArgsConstructor
public class StaffCallCancelRequest {

    private Long tableId;
    private Long cartId;
    private String callType;
}

