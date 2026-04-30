package com.example.spring.service.serving;

import com.example.spring.dto.redis.OrderCookedMessageDto;
import com.example.spring.event.RedisMessageEvent;
import com.example.spring.service.staffcall.StaffCallTableResetService;
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
    private final StaffCallTableResetService staffCallTableResetService;
    private final ObjectMapper objectMapper;

    @EventListener
    @Transactional
    public void handleRedisMessage(RedisMessageEvent event) {
        String channel = event.getChannel();
        String message = event.getMessage();

        if (channel.startsWith("django:booth:") && channel.contains(":order:")) {
            try {
                Long boothId = extractBoothId(channel);
                String orderEvent = extractOrderEvent(channel);
                OrderCookedMessageDto dto = objectMapper.readValue(message, OrderCookedMessageDto.class);

                if ("cooked".equals(orderEvent)) {
                    if (dto.getOrderItemId() == null) {
                        log.warn("[cooked 처리 스킵] order_item_id 누락. channel={}, message={}", channel, message);
                        return;
                    }
                    if (dto.getTableNum() == null) {
                        log.warn("[cooked 처리 경고] table_num/table_number 누락. 생성은 진행하지만 reset-by-table 정리에 실패할 수 있습니다. channel={}, message={}", channel, message);
                    }
                    servingTaskService.createNewServingTask(
                            boothId,
                            dto.getOrderItemId(),
                            dto.getTableNum(),
                            UUID.randomUUID().toString()
                    );
                    log.info("[서빙 태스크 생성 완료] boothId={}, orderItemId={}", boothId, dto.getOrderItemId());
                    return;
                }

                if ("served".equals(orderEvent)) {
                    if (dto.getOrderItemId() == null) {
                        log.warn("[served 처리 스킵] order_item_id 누락. channel={}, message={}", channel, message);
                        return;
                    }
                    servingTaskService.removeTasksByOrderItemId(boothId, dto.getOrderItemId(), "ORDER_SERVED");
                    return;
                }

                if ("cooking".equals(orderEvent)) {
                    if (dto.getOrderItemId() == null) {
                        log.warn("[cooking 처리 스킵] order_item_id 누락. channel={}, message={}", channel, message);
                        return;
                    }
                    servingTaskService.removeTasksByOrderItemId(boothId, dto.getOrderItemId(), "COOKING_ROLLBACK");
                    return;
                }

                if ("reset".equals(orderEvent)) {
                    if (dto.getTableNum() == null) {
                        log.warn("[reset 처리 스킵] table_num/table_number 누락. channel={}, message={}", channel, message);
                        return;
                    }
                    servingTaskService.removeTasksByTableNumber(boothId, dto.getTableNum(), "TABLE_RESET");
                    staffCallTableResetService.voidActiveCallsForTable(boothId, dto.getTableNum());
                }

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

    private String extractOrderEvent(String channel) {
        String[] parts = channel.split(":");
        if (parts.length < 5) {
            throw new IllegalArgumentException("유효하지 않은 채널 형식입니다: " + channel);
        }
        return parts[4];
    }
}