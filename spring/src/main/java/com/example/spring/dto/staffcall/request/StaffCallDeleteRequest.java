package com.example.spring.dto.staffcall.request;

import lombok.Getter;
import lombok.NoArgsConstructor;

/**
 * 고객(무인증)에서 생성 직후 staff_call 삭제 요청에 사용.
 * subscribe_token으로만 삭제 권한을 검증한다.
 */
@Getter
@NoArgsConstructor
public class StaffCallDeleteRequest {
    private Long staffCallId;
    private String subscribeToken;
}

