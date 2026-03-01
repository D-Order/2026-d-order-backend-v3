package com.example.spring.domain.orderitem;

public enum OrderItemStatus {
    COOKING,   // 조리중
    COOKED,    // 조리완료 (Redis 메시지 발행 시점)
    SERVING,   // 서빙중
    SERVED,    // 서빙완료
    CANCELLED  // 취소됨
}