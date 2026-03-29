package com.example.spring.domain.serving;

import com.example.spring.domain.orderitem.OrderItem;
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

    @ManyToOne(fetch = FetchType.LAZY)
    @JoinColumn(name = "orderitem", nullable = false) // 🌟 중요: DB 실제 컬럼명이 orderitem 입니다.
    private OrderItem orderItem;

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

    @Column(name = "key", nullable = false, length = 255) // 소문자 key
    private String key;

    @Builder
    public ServingTask(OrderItem orderItem, String key) {
        this.orderItem = orderItem;
        this.status = ServingStatus.SERVE_REQUESTED;
        this.key = key;
        this.createdAt = LocalDateTime.now();
        this.requestedAt = LocalDateTime.now();
    }

    // 서빙 상태 변경 메서드 (수락)
    public void acceptServing(String catchedBy) {
        this.status = ServingStatus.SERVING;
        this.catchedBy = catchedBy;
        this.catchedAt = LocalDateTime.now();
        this.updatedAt = LocalDateTime.now();
    }

    // 서빙 상태 변경 메서드 (완료)
    public void completeServing() {
        this.status = ServingStatus.SERVED;
        this.servedAt = LocalDateTime.now();
        this.updatedAt = LocalDateTime.now();
    }

    // 서빙 상태 변경 메서드 (취소)
    public void cancelServing() {
        this.status = ServingStatus.SERVE_REQUESTED;
        this.catchedBy = null;
        this.catchedAt = null;
        this.updatedAt = LocalDateTime.now();
    }
}