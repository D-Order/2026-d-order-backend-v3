package com.example.spring.service.serving;

import com.example.spring.dto.redis.OrderCookedMessageDto;
import com.example.spring.event.RedisMessageEvent;
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

    private final ServingTaskService servingTaskService;
    private final ObjectMapper objectMapper;

    @EventListener
    @Transactional
    public void handleRedisMessage(RedisMessageEvent event) {
        String channel = event.getChannel();
        String message = event.getMessage();

        if (channel.startsWith("django:booth:") && channel.endsWith(":order:cooked")) {
            try {
                Long boothId = extractBoothId(channel);
                OrderCookedMessageDto dto = objectMapper.readValue(message, OrderCookedMessageDto.class);

                servingTaskService.createNewServingTask(
                        boothId,
                        dto.getOrderItemId(),
                        UUID.randomUUID().toString()
                );

                log.info("[서빙 태스크 생성 완료] boothId={}, orderItemId={}", boothId, dto.getOrderItemId());

            } catch (Exception e) {
                log.error("[Redis 메시지 처리 실패] channel={}, message={}", channel, message, e);
            }
        }
    }

    /**
     * 예: django:booth:3:order:cooked -> 3 추출
     */
    private Long extractBoothId(String channel) {
        String[] parts = channel.split(":");
        if (parts.length < 5) {
            throw new IllegalArgumentException("유효하지 않은 채널 형식입니다: " + channel);
        }
        return Long.valueOf(parts[2]);
    }
}