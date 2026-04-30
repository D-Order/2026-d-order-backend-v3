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

    @Column(name = "booth_id", nullable = false)
    private Long boothId;

    @Column(name = "orderitem", nullable = false)
    private Long orderItemId;

    @Column(name = "table_number")
    private Integer tableNumber;

    @Column(name = "menu_name")
    private String menuName;

    @Column(name = "quantity")
    private Integer quantity;

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

    @Column(name = "key", nullable = false, length = 255)
    private String key;

    @Builder
    public ServingTask(Long boothId, Long orderItemId, Integer tableNumber, String menuName, Integer quantity, String key) {
        this.boothId = boothId;
        this.orderItemId = orderItemId;
        this.tableNumber = tableNumber;
        this.menuName = menuName;
        this.quantity = quantity;
        this.status = ServingStatus.SERVE_REQUESTED;
        this.key = key;
        this.createdAt = LocalDateTime.now();
        this.requestedAt = LocalDateTime.now();
    }

    public void acceptServing() {
        this.status = ServingStatus.SERVING;
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
        this.catchedAt = null;
        this.updatedAt = LocalDateTime.now();
    }
}