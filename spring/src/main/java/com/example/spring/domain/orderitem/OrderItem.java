package com.example.spring.domain.orderitem;

import jakarta.persistence.*;
import org.hibernate.annotations.Immutable;
import lombok.*;

import java.time.LocalDateTime;

@Entity
@Table(name = "orderitem")
@Immutable // 🌟 핵심 1: Spring이 이 테이블의 데이터를 C/U/D 하지 못하게 '읽기 전용'으로 묶음
@Getter
@NoArgsConstructor(access = AccessLevel.PROTECTED)
public class OrderItem {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    // 🌟 핵심 2: order는 SQL 예약어이므로 반드시 큰따옴표로 감싸서(Escape) 에러를 방지해야 합니다.
    // 기존 데이터와의 충돌(DDL 에러)을 막기 위해 nullable = false를 제거합니다.
    @Column(name = "\"order\"")
    private Long orderId;

    @Column(name = "menu")
    private Long menuId;

    @Column(name = "setmenu")
    private Long setmenuId;

    @Column(name = "parent")
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

    // nullable = false 제거 (Django가 알아서 관리하므로 Spring은 참견하지 않음)
    @Column(name = "key", length = 255)
    private String key;
}