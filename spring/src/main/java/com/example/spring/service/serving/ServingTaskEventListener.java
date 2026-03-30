package com.example.spring.service.serving;

import com.example.spring.domain.serving.ServingTask;
import com.example.spring.dto.redis.OrderCookedMessageDto;
import com.example.spring.dto.serving.response.ServingTaskResponse;
import com.example.spring.event.RedisMessageEvent;
import com.example.spring.repository.orderitem.OrderItemRepository;
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
    private final OrderItemRepository orderItemRepository;
    private final ObjectMapper objectMapper;
    private final ServingWebSocketHandler webSocketHandler; // 웹소캣 핸들러

    @EventListener
    @Transactional
    public void handleRedisMessage(RedisMessageEvent event) {
        String channel = event.getChannel();
        String message = event.getMessage();

        if (channel.startsWith("django:booth:") && channel.endsWith(":order:cooked")) {
            try {
                OrderCookedMessageDto dto = objectMapper.readValue(message, OrderCookedMessageDto.class);

                orderItemRepository.findById(dto.getOrderItemId())
                        .orElseThrow(() -> new IllegalArgumentException("OrderItem not found"));

                ServingTask servingTask = ServingTask.builder()
                        .orderItemId(dto.getOrderItemId())
                        .key(UUID.randomUUID().toString())
                        .build();

                servingTaskRepository.save(servingTask);
                log.info("[서빙 태스크 생성 완료] OrderItemId: {}", dto.getOrderItemId());

                // [웹소켓 추가 부분] DB 저장 끝났으니 프론트 화면으로 바로 쏴주기!
                //프론트 보내는 DTO 만들기
                ServingTaskResponse responseDto = ServingTaskResponse.from(servingTask);
                //JSON으로 바꾸끼
                String jsonResponse = objectMapper.writeValueAsString(responseDto);
                //방송 시작!
                webSocketHandler.broadcastMessage(jsonResponse);

            } catch (Exception e) {
                log.error("[Redis 메시지 처리 실패]", e);
            }
        }
    }
}