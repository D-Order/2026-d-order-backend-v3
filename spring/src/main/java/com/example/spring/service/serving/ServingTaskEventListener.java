package com.example.spring.service.serving;

import com.example.spring.domain.orderitem.OrderItem;
import com.example.spring.domain.serving.ServingTask;
import com.example.spring.dto.redis.OrderCookedMessageDto;
import com.example.spring.event.RedisMessageEvent;
import com.example.spring.repository.orderitem.OrderItemRepository;
import com.example.spring.repository.serving.ServingTaskRepository;
import com.fasterxml.jackson.databind.ObjectMapper;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.context.event.EventListener;
import org.springframework.stereotype.Component;
import org.springframework.transaction.annotation.Transactional;

import java.util.UUID;

@Slf4j
@Component
@RequiredArgsConstructor
public class ServingTaskEventListener {

    private final ServingTaskRepository servingTaskRepository;
    private final OrderItemRepository orderItemRepository;
    private final ObjectMapper objectMapper;

    @EventListener
    @Transactional
    public void handleRedisMessage(RedisMessageEvent event) {
        String channel = event.getChannel();
        String message = event.getMessage();

        // 채널명이 "django:booth:{boothId}:order:cooked" 인지 확인
        if (channel.startsWith("django:booth:") && channel.endsWith(":order:cooked")) {
            try {
                // JSON 메시지를 DTO로 파싱
                OrderCookedMessageDto dto = objectMapper.readValue(message, OrderCookedMessageDto.class);

                // 1. 기존 장고 DB와 매핑되는 OrderItem 조회
                OrderItem orderItem = orderItemRepository.findById(dto.getOrderItemId())
                        .orElseThrow(() -> new IllegalArgumentException("해당 OrderItem을 찾을 수 없습니다: " + dto.getOrderItemId()));

                // 2. 새로운 서빙 태스크 생성 (status는 생성자에서 SERVE_REQUESTED로 자동 세팅됨)
                ServingTask servingTask = ServingTask.builder()
                        .orderItem(orderItem)
                        .key(UUID.randomUUID().toString()) // 고유 Key 생성
                        .build();

                servingTaskRepository.save(servingTask);
                log.info("[서빙 태스크 생성 완료] OrderItemId: {}", dto.getOrderItemId());

            } catch (Exception e) {
                log.error("[Redis 메시지 처리 실패] message: {}", message, e);
            }
        }
    }
}