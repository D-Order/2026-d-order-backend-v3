package com.example.spring.service.serving;

import com.example.spring.dto.redis.OrderCookedMessageDto;
import com.example.spring.event.RedisMessageEvent;
import com.example.spring.domain.staffcall.StaffCall;
import com.example.spring.service.staffcall.StaffCallTableResetService;
import com.fasterxml.jackson.core.JsonProcessingException;
import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.context.event.EventListener;
import org.springframework.stereotype.Component;
import org.springframework.transaction.annotation.Transactional;

import java.util.List;
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
                log.info("[Redis 주문] 수신 boothId={}, 이벤트={}, channel={}, message={}",
                        boothId, orderEvent, channel, truncateForLog(message, 4000));

                OrderCookedMessageDto dto = objectMapper.readValue(message, OrderCookedMessageDto.class);
                log.info("[Redis 주문] JSON 파싱 완료 tableNum={}, orderItemId={}",
                        dto.getTableNum(), dto.getOrderItemId());

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
                    /*
                     * 같은 채널 django:booth:*:order:reset 에 (1) 테이블 초기화용 {"table_num":n}
                     * (2) 서빙취소용 {"order_item_id":...} 가 함께 온다. (2)는 Spring 테이블 초기화와 무관.
                     * table_num 이 문자열이면 DTO Integer 가 null 일 수 있어 JSON 보조 파싱을 먼저 한다.
                     */
                    Integer tableNumFromJson = extractTableNumFromResetJson(message);
                    if (dto.getOrderItemId() != null && dto.getTableNum() == null && tableNumFromJson == null) {
                        log.info("[Redis 주문] order:reset — 테이블 초기화 페이로드 아님(서빙 취소 등) boothId={}, orderItemId={}, 건너뜀",
                                boothId, dto.getOrderItemId());
                        return;
                    }
                    Integer tableNum = dto.getTableNum() != null ? dto.getTableNum() : tableNumFromJson;
                    if (tableNum == null) {
                        log.warn("[테이블 초기화 처리 스킵] table_num 없음·파싱 불가. channel={}, message={}",
                                channel, truncateForLog(message, 2000));
                        return;
                    }
                    log.info("[테이블 초기화] 서빙태스크 삭제 직전 boothId={}, tableNum={}", boothId, tableNum);
                    servingTaskService.removeTasksByTableNumber(boothId, tableNum, "TABLE_RESET");
                    log.info("[테이블 초기화] staff_call 취소 호출 직전 boothId={}, tableNum={}", boothId, tableNum);
                    List<StaffCall> voided = staffCallTableResetService.voidActiveCallsForTable(
                            boothId, tableNum);
                    log.info("[테이블 초기화] 스냅샷·WS 호출 직전 boothId={}, staffCall취소건수={}",
                            boothId, voided.size());
                    staffCallTableResetService.publishTableResetNotifications(boothId, voided);
                    log.info("[테이블 초기화] 처리 완료 boothId={}, tableNum={}, staffCall취소건수={}",
                            boothId, tableNum, voided.size());
                    return;
                }

                log.warn("[Redis 주문] 미처리 이벤트 이벤트={}, boothId={}, channel={}, message={}",
                        orderEvent, boothId, channel, truncateForLog(message, 1000));

            } catch (JsonProcessingException e) {
                log.error("[Redis 주문] JSON 파싱 실패 channel={}, message={}",
                        channel, truncateForLog(message, 4000), e);
            } catch (Exception e) {
                log.error("[Redis 주문] 처리 실패 channel={}, message={}",
                        channel, truncateForLog(message, 4000), e);
            }
        }
    }

    /** JSON에 table_num 이 문자열 등으로만 있을 때 보조 파싱 */
    private Integer extractTableNumFromResetJson(String message) {
        try {
            JsonNode root = objectMapper.readTree(message);
            Integer n = readIntFlexible(root.get("table_num"));
            if (n != null) {
                return n;
            }
            return readIntFlexible(root.get("table_number"));
        } catch (Exception e) {
            log.warn("[테이블 초기화] table_num JSON 보조 파싱 실패: {}", e.getMessage());
            return null;
        }
    }

    private static Integer readIntFlexible(JsonNode node) {
        if (node == null || node.isNull()) {
            return null;
        }
        if (node.isInt() || node.isLong()) {
            return node.intValue();
        }
        if (node.isTextual()) {
            try {
                return Integer.parseInt(node.asText().trim());
            } catch (NumberFormatException ignored) {
                return null;
            }
        }
        return null;
    }

    private static String truncateForLog(String s, int maxChars) {
        if (s == null) {
            return "null";
        }
        if (s.length() <= maxChars) {
            return s;
        }
        return s.substring(0, maxChars) + "…(truncated " + s.length() + " chars)";
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