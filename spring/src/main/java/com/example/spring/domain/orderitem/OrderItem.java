package com.example.spring.domain.orderitem;

import jakarta.persistence.*;
import lombok.*;
import java.time.LocalDateTime;

@Entity
@Table(name = "orderitem") // 소문자로 통일
@Getter
@NoArgsConstructor(access = AccessLevel.PROTECTED)
public class OrderItem {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    @Column(name = "order", nullable = false) // DB 결과에 따라 언더바 제거
    private Long orderId;

    @Column(name = "menu", nullable = false) // DB 결과와 일치
    private Long menuId;

    @Column(name = "setmenu", nullable = false) // DB 결과와 일치
    private Long setmenuId;

    @Column(name = "parent", nullable = false) // DB 결과와 일치
    private Long parentId;

    @Column(name = "quantity")
    private Integer quantity;

    @Column(name = "fixed_price")
    private Integer fixedPrice;

    @Enumerated(EnumType.STRING)
    @Column(name = "status")
    private OrderItemStatus status;

    @Column(name = "created_at")
    private LocalDateTime createdAt;

    @Column(name = "cooked_at")
    private LocalDateTime cookedAt;

    @Column(name = "served_at")
    private LocalDateTime servedAt;

    @Column(name = "key", nullable = false, length = 255) // 소문자 key
    private String key;
}