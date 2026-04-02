package com.example.spring.repository.cart;

import com.example.spring.domain.cart.CartEntity;
import org.springframework.data.jpa.repository.JpaRepository;

public interface CartEntityRepository extends JpaRepository<CartEntity, Long> {
}
