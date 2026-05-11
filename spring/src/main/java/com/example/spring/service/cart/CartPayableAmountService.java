package com.example.spring.service.cart;

import com.example.spring.domain.cart.CartEntity;
import com.example.spring.repository.cart.CartEntityRepository;
import lombok.RequiredArgsConstructor;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Service;

import java.math.BigDecimal;
import java.util.List;
import java.util.Optional;

/**
 * Django {@code cart.services._calc_discount} + {@code build_cart_snapshot_data}와 동일한 규칙으로
 * 쿠폰 적용 후 실제 부담 금액(소계 − 할인)을 계산한다.
 * <p>
 * {@code cart_cart.cart_price}는 항상 품목 합(쿠폰 전)이므로, 쿠폰은 {@code coupon_cartcouponapply}에서 조회한다.
 */
@Service
@RequiredArgsConstructor
public class CartPayableAmountService {

    private final CartEntityRepository cartEntityRepository;
    private final JdbcTemplate jdbcTemplate;

    /**
     * @return 쿠폰 반영 금액(0 이상). 쿠폰 없으면 {@code cart_price}와 동일.
     */
    public int resolvePayableTotal(long cartId) {
        CartEntity cart = cartEntityRepository.findById(cartId)
                .orElseThrow(() -> new IllegalArgumentException("카트를 찾을 수 없습니다."));
        return resolvePayableTotal(cart);
    }

    public int resolvePayableTotal(CartEntity cart) {
        int subtotal = cart.getCartPrice() != null ? cart.getCartPrice() : 0;
        int round = cart.getRound() != null ? cart.getRound() : 0;

        Optional<DiscountRow> applied = findAppliedCoupon(cart.getId(), round);
        if (applied.isEmpty()) {
            return subtotal;
        }
        int discount = calcDiscount(subtotal, applied.get().discountType(), applied.get().discountValue());
        return Math.max(0, subtotal - discount);
    }

    private Optional<DiscountRow> findAppliedCoupon(long cartId, int round) {
        String sql = """
                SELECT cp.discount_type, cp.discount_value
                FROM coupon_cartcouponapply a
                JOIN coupon_couponcode cc ON a.coupon_code_id = cc.id
                JOIN coupon_coupon cp ON cc.coupon_id = cp.id
                WHERE a.cart_id = ? AND a.round = ?
                LIMIT 1
                """;
        List<DiscountRow> rows = jdbcTemplate.query(sql, (rs, rowNum) -> new DiscountRow(
                rs.getString("discount_type"),
                rs.getBigDecimal("discount_value")
        ), cartId, round);
        return rows.stream().findFirst();
    }

    /**
     * Django {@code _calc_discount} 이식
     */
    private static int calcDiscount(int subtotal, String discountType, BigDecimal discountValue) {
        if (subtotal <= 0) {
            return 0;
        }
        if (discountValue == null) {
            return 0;
        }
        if ("RATE".equals(discountType)) {
            int amt = (int) (subtotal * discountValue.doubleValue());
            return Math.max(0, Math.min(subtotal, amt));
        }
        int amt = discountValue.intValue();
        return Math.max(0, Math.min(subtotal, amt));
    }

    private record DiscountRow(String discountType, BigDecimal discountValue) {
    }
}
