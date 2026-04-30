package com.example.spring.service.staffcall;

import com.example.spring.config.DjangoApiUtil;
import com.example.spring.domain.staffcall.StaffCall;
import com.example.spring.domain.staffcall.StaffCallStatus;
import com.example.spring.dto.redis.StaffCallRedisMessageDto;
import com.example.spring.repository.staffcall.StaffCallRepository;
import com.example.spring.websocket.CustomerStaffCallWebSocketHandler;
import com.example.spring.websocket.StaffCallWebSocketHandler;
import com.fasterxml.jackson.databind.ObjectMapper;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.http.*;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
import org.springframework.data.redis.core.StringRedisTemplate;
import org.springframework.web.client.HttpClientErrorException;
import org.springframework.web.client.RestTemplate;

import java.time.LocalDateTime;
import java.util.HashMap;
import java.util.Map;

/**
 * 직원/운영 화면의 "주문 취소"를 단일 API로 처리하기 위한 오케스트레이션 서비스.
 *
 * 목표: Django 결제취소 성공 시에만 staffcall을 삭제하고, 마지막에 커스터머 WS로 DELETED를 1회 푸시한다.
 */
@Slf4j
@Service
@RequiredArgsConstructor
public class OrderCancelService {

    private final RestTemplate restTemplate;
    private final ObjectMapper objectMapper;
    private final StaffCallRepository staffCallRepository;
    private final StaffCallQueryService staffCallQueryService;
    private final StaffCallWebSocketHandler staffCallWebSocketHandler;
    private final CustomerStaffCallWebSocketHandler customerStaffCallWebSocketHandler;
    private final StringRedisTemplate redisTemplate;

    @Value("${django.api.base-url}")
    private String djangoApiBaseUrl;

    @Transactional
    public Map<String, Object> cancelOrder(Long boothId, Long staffCallId) {
        if (boothId == null) {
            throw new IllegalArgumentException("booth_id를 확인할 수 없습니다.");
        }
        if (staffCallId == null) {
            throw new IllegalArgumentException("staff_call_id는 필수입니다.");
        }

        StaffCall sc = staffCallRepository.findById(staffCallId)
                .orElseThrow(() -> new IllegalArgumentException("해당 호출을 찾을 수 없습니다."));

        if (!boothId.equals(sc.getBoothId())) {
            throw new IllegalArgumentException("부스 정보가 일치하지 않습니다.");
        }

        if (sc.getTableUsageId() == null) {
            throw new StaffCallConflictException("table_usage_id가 없어 결제 취소를 진행할 수 없습니다.");
        }

        if (sc.getStatus() == StaffCallStatus.COMPLETED || sc.getStatus() == StaffCallStatus.CANCELLED) {
            throw new StaffCallConflictException("이미 처리된 호출입니다.");
        }

        // 1) Django 결제취소 (실패 시 staffcall은 건드리지 않음)
        callDjangoPaymentCancel(sc.getTableUsageId());

        // 2) staffcall 정리 (PENDING/ACCEPTED만 삭제 허용)
        if (sc.getStatus() != StaffCallStatus.PENDING && sc.getStatus() != StaffCallStatus.ACCEPTED) {
            throw new StaffCallConflictException("취소할 수 없는 staffcall 상태입니다.");
        }

        staffCallRepository.delete(sc);

        // 3) 이벤트 발행/푸시 (마지막에 DELETED 1회)
        publishRedis(sc, "staff_call_deleted");
        try {
            staffCallWebSocketHandler.broadcastSnapshot(boothId,
                    staffCallQueryService.listForBooth(boothId, 50, 0));
            customerStaffCallWebSocketHandler.broadcastDeleted(staffCallId);
        } catch (Exception e) {
            log.error("[order cancel] 스냅샷 조회/WS 푸시 실패 — 취소는 반영됨 boothId={}", boothId, e);
        }

        Map<String, Object> out = new HashMap<>();
        out.put("message", "주문이 취소되었습니다.");
        out.put("data", Map.of(
                "staff_call_id", staffCallId,
                "table_usage_id", sc.getTableUsageId()
        ));
        return out;
    }

    private void callDjangoPaymentCancel(Long tableUsageId) {
        String url = djangoApiBaseUrl + "/api/v3/django/cart/payment-cancel/";

        Map<String, String> csrfData = DjangoApiUtil.getCsrfToken(restTemplate, djangoApiBaseUrl);
        Map<String, Object> requestBody = Map.of("table_usage_id", tableUsageId);

        String jsonBody;
        try {
            jsonBody = objectMapper.writeValueAsString(requestBody);
        } catch (Exception e) {
            throw new RuntimeException("JSON 변환 실패", e);
        }

        HttpHeaders headers = new HttpHeaders();
        headers.setContentType(MediaType.APPLICATION_JSON);
        if (csrfData.get("csrfToken") != null) headers.set("X-CSRFToken", csrfData.get("csrfToken"));
        if (csrfData.get("csrfCookie") != null) headers.set(HttpHeaders.COOKIE, csrfData.get("csrfCookie"));

        try {
            restTemplate.exchange(url, HttpMethod.POST, new HttpEntity<>(jsonBody, headers), Map.class);
        } catch (HttpClientErrorException e) {
            // Django 오류 바디를 그대로 전달하는 대신, 현재 서비스 메시지 규칙에 맞춰 변환
            HttpStatus status = HttpStatus.valueOf(e.getStatusCode().value());
            if (status == HttpStatus.CONFLICT) {
                throw new StaffCallConflictException("결제 취소가 가능한 상태가 아닙니다.");
            }
            throw new StaffCallConflictException("결제 취소 처리에 실패했습니다.");
        }
    }

    private void publishRedis(StaffCall sc, String event) {
        try {
            StaffCallRedisMessageDto dto = StaffCallRedisMessageDto.builder()
                    .event(event)
                    .staffCallId(sc.getId())
                    .boothId(sc.getBoothId())
                    .tableId(sc.getTableId())
                    .cartId(sc.getCartId())
                    .tableUsageId(sc.getTableUsageId())
                    .tableNum(sc.getTableNum())
                    .cartPrice(sc.getCartPrice())
                    .callType(sc.getCallType())
                    .category(sc.getCategory() != null ? sc.getCategory().name() : null)
                    .status(sc.getStatus() != null ? sc.getStatus().name() : null)
                    .pushedAt(LocalDateTime.now())
                    .build();

            String json = objectMapper.writeValueAsString(dto);
            String channel = "spring:booth:" + sc.getBoothId() + ":staffcall:" + event.replace("staff_call_", "");
            redisTemplate.convertAndSend(channel, json);
            log.info("[Redis staffcall] {}", channel);
        } catch (Exception e) {
            log.error("[Redis staffcall 발행 실패]", e);
        }
    }
}

