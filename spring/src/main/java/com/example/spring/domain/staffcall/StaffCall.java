package com.example.spring.domain.staffcall;

import jakarta.persistence.*;
import lombok.*;

import java.time.LocalDateTime;

@Entity
@Table(name = "staff_call")
@Getter
@NoArgsConstructor(access = AccessLevel.PROTECTED)
public class StaffCall {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    /** JWT booth_id와 동일 — 조회/검증용 비정규화 */
    @Column(name = "booth_id", nullable = false)
    private Long boothId;

    @Column(name = "table_id", nullable = false)
    private Long tableId;

    @Column(name = "cart_id", nullable = false)
    private Long cartId;

    /** 비즈니스 호출 종류(물, 계산서 등) */
    @Column(name = "call_type", nullable = false, length = 64)
    private String callType;

    @Enumerated(EnumType.STRING)
    @Column(name = "category", nullable = false, length = 16)
    private StaffCallCategory category;

    @Enumerated(EnumType.STRING)
    @Column(name = "status", nullable = false, length = 16)
    private StaffCallStatus status;

    @Column(name = "created_at", nullable = false)
    private LocalDateTime createdAt;

    @Column(name = "accepted_at")
    private LocalDateTime acceptedAt;

    @Column(name = "accepted_by", length = 255)
    private String acceptedBy;

    @Column(name = "completed_at")
    private LocalDateTime completedAt;

    @Version
    @Column(name = "version")
    private Long version;

    @Builder
    public StaffCall(Long boothId, Long tableId, Long cartId, String callType, StaffCallCategory category) {
        this.boothId = boothId;
        this.tableId = tableId;
        this.cartId = cartId;
        this.callType = callType;
        this.category = category;
        this.status = StaffCallStatus.PENDING;
        this.createdAt = LocalDateTime.now();
    }

    public void accept(String acceptedBy) {
        this.status = StaffCallStatus.ACCEPTED;
        this.acceptedAt = LocalDateTime.now();
        this.acceptedBy = acceptedBy;
    }
}
