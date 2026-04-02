package com.example.spring.dto.staffcall.request;

import com.example.spring.domain.staffcall.StaffCallCategory;
import lombok.Getter;
import lombok.NoArgsConstructor;

/**
 * 직원 호출 발생(태블릿 등) — serving / general 구분
 */
@Getter
@NoArgsConstructor
public class StaffCallEmitRequest {

    private Long tableId;
    private Long cartId;
    /** 예: WATER, BILL 등 */
    private String callType;
    /** SERVING: 서빙 연계, GENERAL: 일반 직원 호출 */
    private StaffCallCategory category;
}
