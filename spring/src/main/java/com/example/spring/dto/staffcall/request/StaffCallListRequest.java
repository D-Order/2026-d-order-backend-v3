package com.example.spring.dto.staffcall.request;

import lombok.Getter;
import lombok.NoArgsConstructor;

/**
 * 은호님 의견: booth_id는 JWT로 충분 — 바디에서는 limit/offset(또는 cursor)만 사용
 */
@Getter
@NoArgsConstructor
public class StaffCallListRequest {

    private int limit = 20;

    private int offset = 0;
}
