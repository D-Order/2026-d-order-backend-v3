package com.example.spring.service.staffcall;

/**
 * 동시 수락 시 먼저 도달한 요청만 성공 — 나머지는 409
 */
public class StaffCallConflictException extends RuntimeException {
    public StaffCallConflictException(String message) {
        super(message);
    }
}
