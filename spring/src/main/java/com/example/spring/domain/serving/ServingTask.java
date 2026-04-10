package com.example.spring.domain.serving;

import jakarta.persistence.*;
import lombok.*;

import java.time.LocalDateTime;

@Entity
@Table(name = "serving_task")
@Getter
@NoArgsConstructor(access = AccessLevel.PROTECTED)
public class ServingTask {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    /**
     * 운영자 인증 기반 조회를 위해 serving_task 자체에 booth_id를 저장
     */
    @Column(name = "booth_id", nullable = false)
    private Long boothId;

    /**
     * Django가 관리하는 orderitem 테이블은
     * Spring에서 JPA 연관관계로 직접 물지 않고 FK 값(ID)만 저장
     */
    @Column(name = "orderitem", nullable = false)
    private Long orderItemId;

    @Enumerated(EnumType.STRING)
    @Column(name = "status")
    private ServingStatus status;

    @Column(name = "created_at")
    private LocalDateTime createdAt;

    @Column(name = "updated_at")
    private LocalDateTime updatedAt;

    @Column(name = "requested_at")
    private LocalDateTime requestedAt;

    @Column(name = "catched_at")
    private LocalDateTime catchedAt;

    @Column(name = "served_at")
    private LocalDateTime servedAt;

    @Column(name = "catched_by")
    private String catchedBy;

    @Column(name = "key", nullable = false, length = 255)
    private String key;

    @Builder
    public ServingTask(Long boothId, Long orderItemId, String key) {
        this.boothId = boothId;
        this.orderItemId = orderItemId;
        this.status = ServingStatus.SERVE_REQUESTED;
        this.key = key;
        this.createdAt = LocalDateTime.now();
        this.requestedAt = LocalDateTime.now();
    }

    public void acceptServing(String catchedBy) {
        this.status = ServingStatus.SERVING;
        this.catchedBy = catchedBy;
        this.catchedAt = LocalDateTime.now();
        this.updatedAt = LocalDateTime.now();
    }

    public void completeServing() {
        this.status = ServingStatus.SERVED;
        this.servedAt = LocalDateTime.now();
        this.updatedAt = LocalDateTime.now();
    }

    public void cancelServing() {
        this.status = ServingStatus.SERVE_REQUESTED;
        this.catchedBy = null;
        this.catchedAt = null;
        this.updatedAt = LocalDateTime.now();
    }
}