package com.example.spring.service.serving;

import com.example.spring.domain.serving.ServingTask;
import com.example.spring.dto.redis.OrderCookedMessageDto;
import com.example.spring.dto.serving.response.ServingTaskResponse;
import com.example.spring.event.RedisMessageEvent;
import com.example.spring.repository.serving.ServingTaskRepository;
import com.example.spring.websocket.ServingWebSocketHandler;
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
    // 🌟 OrderItem 연관관계를 끊었으므로 OrderItemRepository 제거
    private final ObjectMapper objectMapper;
    private final ServingWebSocketHandler webSocketHandler;

    @EventListener
    @Transactional
    public void handleRedisMessage(RedisMessageEvent event) {
        String channel = event.getChannel();
        String message = event.getMessage();

        if (channel.startsWith("django:booth:") && channel.endsWith(":order:cooked")) {
            try {
                OrderCookedMessageDto dto = objectMapper.readValue(message, OrderCookedMessageDto.class);

                // 🌟 Spring에서 직접 OrderItem을 DB에서 검증하던 로직 제거 (Django 소유 테이블)

                ServingTask servingTask = ServingTask.builder()
                        .orderItemId(dto.getOrderItemId())
                        .key(UUID.randomUUID().toString()) // 기존 UUID 생성 로직 유지
                        .build();

                servingTaskRepository.save(servingTask);
                log.info("[서빙 태스크 생성 완료] OrderItemId: {}", dto.getOrderItemId());

                // [웹소켓 추가 부분] DB 저장 끝났으니 프론트 화면으로 바로 쏴주기!
                ServingTaskResponse responseDto = ServingTaskResponse.from(servingTask);

                // 🌟 JSON 타입 분류("NEW_CALL")를 포함하여 프론트엔드 친화적으로 브로드캐스트
                webSocketHandler.broadcastEvent("NEW_CALL", responseDto);

            } catch (Exception e) {
                log.error("[Redis 메시지 처리 실패]", e);
            }
        }
    }
}