package com.example.spring.domain.orderitem;

import jakarta.persistence.*;
import lombok.*;
import java.time.LocalDateTime;

@Entity
@Table(name = "`Orderitem`")
@Getter
@NoArgsConstructor(access = AccessLevel.PROTECTED)
public class OrderItem {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    @Column(name = "`order`", nullable = false)
    private Long orderId;

    @Column(name = "menu", nullable = false)
    private Long menuId;

    @Column(name = "setmenu", nullable = false)
    private Long setmenuId;

    @Column(name = "parent", nullable = false)
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

    @Column(name = "`Key`", nullable = false, length = 255)
    private String key;
}