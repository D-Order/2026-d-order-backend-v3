package com.example.spring.domain.staffcall;

/**
 * 서빙 연계 호출 vs 일반 직원 호출 구분 (Redis/WebSocket/API 공통)
 */
public enum StaffCallCategory {
    SERVING,
    GENERAL
}
