package com.example.spring.service.staffcall;

import com.example.spring.config.JwtUtil;
import com.example.spring.domain.cart.CartEntity;
import com.example.spring.domain.staffcall.StaffCall;
import com.example.spring.domain.staffcall.StaffCallStatus;
import com.example.spring.domain.table.BoothTable;
import com.example.spring.domain.table.TableUsageEntity;
import com.example.spring.dto.redis.StaffCallRedisMessageDto;
import com.example.spring.dto.staffcall.request.StaffCallAcceptRequest;
import com.example.spring.dto.staffcall.request.StaffCallEmitRequest;
import com.example.spring.dto.staffcall.response.StaffCallAcceptResponse;
import com.example.spring.dto.staffcall.response.StaffCallItemResponse;
import com.example.spring.repository.cart.CartEntityRepository;
import com.example.spring.repository.staffcall.StaffCallRepository;
import com.example.spring.repository.table.BoothTableRepository;
import com.example.spring.repository.table.TableUsageEntityRepository;
import com.example.spring.websocket.StaffCallWebSocketHandler;
import com.fasterxml.jackson.databind.ObjectMapper;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.context.annotation.Lazy;
import org.springframework.data.redis.core.StringRedisTemplate;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.time.LocalDateTime;
import java.util.HashMap;
import java.util.Map;

@Slf4j
@Service
@RequiredArgsConstructor
public class StaffCallService {

    private final StaffCallRepository staffCallRepository;
    private final StaffCallQueryService staffCallQueryService;
    private final BoothTableRepository boothTableRepository;
    private final CartEntityRepository cartEntityRepository;
    private final TableUsageEntityRepository tableUsageEntityRepository;
    private final JwtUtil jwtUtil;
    private final ObjectMapper objectMapper;
    private final StringRedisTemplate redisTemplate;

    @Lazy
    @Autowired
    private StaffCallWebSocketHandler staffCallWebSocketHandler;

    @Transactional
    public StaffCallAcceptResponse accept(Long boothId, String accessToken, StaffCallAcceptRequest req) {
        if (req.getTableId() == null || req.getCartId() == null || req.getCallType() == null) {
            throw new IllegalArgumentException("table_id, cart_id, call_type은 필수입니다.");
        }

        StaffCall sc = staffCallRepository
                .findByTableCartCallTypeForUpdate(req.getTableId(), req.getCartId(), req.getCallType())
                .orElseThrow(() -> new IllegalArgumentException("해당 호출을 찾을 수 없습니다."));

        if (!boothId.equals(sc.getBoothId())) {
            throw new IllegalArgumentException("부스 정보가 일치하지 않습니다.");
        }

        if (sc.getStatus() != StaffCallStatus.PENDING) {
            throw new StaffCallConflictException("이미 처리된 요청입니다.");
        }

        String acceptedBy = jwtUtil.getUsernameFromToken(accessToken);
        if (acceptedBy == null || acceptedBy.isBlank()) {
            acceptedBy = "unknown";
        }

        sc.accept(acceptedBy);

        publishRedis(sc, "staff_call_accepted");
        staffCallWebSocketHandler.broadcastSnapshot(boothId, staffCallQueryService.listForBooth(boothId, 50, 0));

        return StaffCallAcceptResponse.builder()
                .tableId(sc.getTableId())
                .cartId(sc.getCartId())
                .callType(sc.getCallType())
                .status(sc.getStatus().name())
                .acceptedAt(sc.getAcceptedAt())
                .acceptedBy(sc.getAcceptedBy())
                .build();
    }

    @Transactional
    public Map<String, Object> emit(Long boothId, StaffCallEmitRequest req) {
        if (req.getTableId() == null || req.getCartId() == null || req.getCallType() == null || req.getCategory() == null) {
            throw new IllegalArgumentException("table_id, cart_id, call_type, category는 필수입니다.");
        }

        BoothTable table = boothTableRepository.findByIdAndBoothId(req.getTableId(), boothId)
                .orElseThrow(() -> new IllegalArgumentException("테이블을 찾을 수 없거나 부스가 일치하지 않습니다."));

        if (!"AVAILABLE".equals(table.getStatus()) && !"IN_USE".equals(table.getStatus())) {
            throw new IllegalArgumentException("비활성 테이블에서는 호출할 수 없습니다.");
        }

        CartEntity cart = cartEntityRepository.findById(req.getCartId())
                .orElseThrow(() -> new IllegalArgumentException("카트를 찾을 수 없습니다."));

        TableUsageEntity usage = tableUsageEntityRepository.findById(cart.getTableUsageId())
                .orElseThrow(() -> new IllegalArgumentException("테이블 사용 정보를 찾을 수 없습니다."));

        if (!usage.getTableId().equals(req.getTableId())) {
            throw new IllegalArgumentException("카트와 테이블이 일치하지 않습니다.");
        }

        long pendingDup = staffCallRepository.countByTableIdAndCartIdAndCallTypeAndStatus(
                req.getTableId(), req.getCartId(), req.getCallType(), StaffCallStatus.PENDING);
        if (pendingDup > 0) {
            throw new StaffCallConflictException("동일한 호출이 이미 대기 중입니다.");
        }

        StaffCall sc = StaffCall.builder()
                .boothId(boothId)
                .tableId(req.getTableId())
                .cartId(req.getCartId())
                .callType(req.getCallType())
                .category(req.getCategory())
                .build();

        staffCallRepository.save(sc);

        publishRedis(sc, "staff_call_created");
        staffCallWebSocketHandler.broadcastSnapshot(boothId, staffCallQueryService.listForBooth(boothId, 50, 0));

        Map<String, Object> out = new HashMap<>();
        out.put("message", "직원 호출이 등록되었습니다.");
        out.put("data", StaffCallItemResponse.from(sc));
        return out;
    }

    private void publishRedis(StaffCall sc, String event) {
        try {
            StaffCallRedisMessageDto dto = StaffCallRedisMessageDto.builder()
                    .event(event)
                    .staffCallId(sc.getId())
                    .boothId(sc.getBoothId())
                    .tableId(sc.getTableId())
                    .cartId(sc.getCartId())
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
