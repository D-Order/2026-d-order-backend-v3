package com.example.spring.domain.cart;

import jakarta.persistence.*;
import lombok.AccessLevel;
import lombok.Getter;
import lombok.NoArgsConstructor;

/**
 * Django {@code cart.Cart} → {@code cart_cart}
 */
@Entity
@Table(name = "cart_cart")
@Getter
@NoArgsConstructor(access = AccessLevel.PROTECTED)
public class CartEntity {

    @Id
    private Long id;

    @Column(name = "table_usage_id", nullable = false)
    private Long tableUsageId;

    /** Django cart_cart.cart_price — 장바구니 총 금액 */
    @Column(name = "cart_price", nullable = false)
    private Integer cartPrice;
}
