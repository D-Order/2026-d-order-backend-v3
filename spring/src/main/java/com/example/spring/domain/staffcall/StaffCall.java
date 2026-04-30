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

    /** Django cart.table_usage_id — 결제확인 시 Django에 전달하기 위한 비정규화 */
    @Column(name = "table_usage_id")
    private Long tableUsageId;

    /** Django table_table.table_num — 프론트 표시용 테이블 번호 */
    @Column(name = "table_num")
    private Integer tableNum;

    /** emit 시점 부담 금액(쿠폰 할인 반영). Django 장바구니 스냅샷 summary.total 과 맞춤 */
    @Column(name = "cart_price")
    private Integer cartPrice;

    /** 비즈니스 호출 종류(물, 계산서 등) */
    @Column(name = "call_type", nullable = false, length = 64)
    private String callType;

    @Enumerated(EnumType.STRING)
    @Column(name = "category", nullable = false, length = 16)
    private StaffCallCategory category;

    @Enumerated(EnumType.STRING)
    @Column(name = "status", nullable = false, length = 32)
    private StaffCallStatus status;

    @Column(name = "created_at", nullable = false)
    private LocalDateTime createdAt;

    @Column(name = "updated_at", nullable = false)
    private LocalDateTime updatedAt;

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
    public StaffCall(Long boothId, Long tableId, Long tableUsageId, Integer tableNum, Integer cartPrice,
                     Long cartId, String callType, StaffCallCategory category) {
        this.boothId = boothId;
        this.tableId = tableId;
        this.tableUsageId = tableUsageId;
        this.tableNum = tableNum;
        this.cartPrice = cartPrice;
        this.cartId = cartId;
        this.callType = callType;
        this.category = category;
        this.status = StaffCallStatus.PENDING;
        this.createdAt = LocalDateTime.now();
        this.updatedAt = this.createdAt;
    }

    public void accept(String acceptedBy) {
        this.status = StaffCallStatus.ACCEPTED;
        this.acceptedAt = LocalDateTime.now();
        this.acceptedBy = acceptedBy;
        this.updatedAt = this.acceptedAt;
    }

    public void unaccept() {
        this.status = StaffCallStatus.PENDING;
        this.acceptedAt = null;
        this.acceptedBy = null;
        this.updatedAt = LocalDateTime.now();
    }

    public void complete() {
        this.status = StaffCallStatus.COMPLETED;
        this.completedAt = LocalDateTime.now();
        this.updatedAt = this.completedAt;
    }

    /** Django 테이블 초기화로 세션이 끊긴 경우 — 활성 호출만 목록에서 제외. */
    public void cancelDueToTableReset() {
        if (this.status != StaffCallStatus.PENDING && this.status != StaffCallStatus.ACCEPTED) {
            return;
        }
        this.status = StaffCallStatus.VOIDED_BY_RESET;
        this.updatedAt = LocalDateTime.now();
    }
}
