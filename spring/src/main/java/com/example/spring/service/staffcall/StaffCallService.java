package com.example.spring.service.staffcall;

import com.example.spring.config.JwtUtil;
import com.example.spring.domain.cart.CartEntity;
import com.example.spring.domain.staffcall.StaffCall;
import com.example.spring.domain.staffcall.StaffCallStatus;
import com.example.spring.domain.table.BoothTable;
import com.example.spring.domain.table.TableUsageEntity;
import com.example.spring.dto.redis.StaffCallRedisMessageDto;
import com.example.spring.dto.staffcall.request.StaffCallAcceptRequest;
import com.example.spring.dto.staffcall.request.StaffCallCancelRequest;
import com.example.spring.dto.staffcall.request.StaffCallCompleteRequest;
import com.example.spring.dto.staffcall.request.StaffCallDeleteRequest;
import com.example.spring.dto.staffcall.request.StaffCallEmitRequest;
import com.example.spring.dto.staffcall.response.StaffCallAcceptResponse;
import com.example.spring.dto.staffcall.response.StaffCallItemResponse;
import com.example.spring.service.cart.CartPayableAmountService;
import com.example.spring.repository.cart.CartEntityRepository;
import com.example.spring.repository.staffcall.StaffCallRepository;
import com.example.spring.repository.table.BoothTableRepository;
import com.example.spring.repository.table.TableUsageEntityRepository;
import com.example.spring.websocket.CustomerStaffCallWebSocketHandler;
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
import java.util.List;
import java.util.Map;

@Slf4j
@Service
@RequiredArgsConstructor
public class StaffCallService {

    private final StaffCallRepository staffCallRepository;
    private final StaffCallQueryService staffCallQueryService;
    private final BoothTableRepository boothTableRepository;
    private final CartEntityRepository cartEntityRepository;
    private final CartPayableAmountService cartPayableAmountService;
    private final TableUsageEntityRepository tableUsageEntityRepository;
    private final JwtUtil jwtUtil;
    private final ObjectMapper objectMapper;
    private final StringRedisTemplate redisTemplate;

    @Lazy
    @Autowired
    private StaffCallWebSocketHandler staffCallWebSocketHandler;

    @Lazy
    @Autowired
    private CustomerStaffCallWebSocketHandler customerStaffCallWebSocketHandler;

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
            if (sc.getStatus() == StaffCallStatus.ACCEPTED) {
                throw new StaffCallConflictException("이미 수락된 요청입니다.");
            }
            throw new StaffCallConflictException("이미 처리된 요청입니다.");
        }

        String acceptedBy = jwtUtil.getUsernameFromToken(accessToken);
        if (acceptedBy == null || acceptedBy.isBlank()) {
            acceptedBy = "unknown";
        }

        sc.accept(acceptedBy);

        publishRedis(sc, "staff_call_accepted");
        try {
            staffCallWebSocketHandler.broadcastSnapshot(boothId,
                    staffCallQueryService.listForBooth(boothId, 50, 0));
            customerStaffCallWebSocketHandler.broadcastStatus(sc);
        } catch (Exception e) {
            log.error("[staffcall accept] 스냅샷 조회/WS 푸시 실패 — 수락은 반영됨 boothId={}", boothId, e);
        }

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
    public Map<String, Object> cancelAccept(Long boothId, String accessToken, StaffCallCancelRequest req) {
        if (req.getTableId() == null || req.getCartId() == null || req.getCallType() == null) {
            throw new IllegalArgumentException("table_id, cart_id, call_type은 필수입니다.");
        }

        StaffCall sc = staffCallRepository
                .findByTableCartCallTypeForUpdate(req.getTableId(), req.getCartId(), req.getCallType())
                .orElseThrow(() -> new IllegalArgumentException("해당 호출을 찾을 수 없습니다."));

        if (!boothId.equals(sc.getBoothId())) {
            throw new IllegalArgumentException("부스 정보가 일치하지 않습니다.");
        }

        // 멱등성: 이미 PENDING이면 취소된 상태로 간주하고 그대로 성공 처리
        if (sc.getStatus() == StaffCallStatus.PENDING) {
            Map<String, Object> out = new HashMap<>();
            out.put("message", "이미 호출 수락이 취소된 상태입니다.");
            out.put("data", StaffCallItemResponse.from(sc));
            return out;
        }

        if (sc.getStatus() != StaffCallStatus.ACCEPTED) {
            throw new StaffCallConflictException("수락된 호출만 취소할 수 있습니다.");
        }

        String actor = jwtUtil.getUsernameFromToken(accessToken);
        if (actor != null && !actor.isBlank() && sc.getAcceptedBy() != null && !sc.getAcceptedBy().equals(actor)) {
            throw new StaffCallConflictException("다른 사용자가 수락한 호출은 취소할 수 없습니다.");
        }

        sc.unaccept();

        publishRedis(sc, "staff_call_unaccepted");
        try {
            staffCallWebSocketHandler.broadcastSnapshot(boothId,
                    staffCallQueryService.listForBooth(boothId, 50, 0));
            customerStaffCallWebSocketHandler.broadcastStatus(sc);
        } catch (Exception e) {
            log.error("[staffcall cancelAccept] 스냅샷 조회/WS 푸시 실패 — 취소는 반영됨 boothId={}", boothId, e);
        }

        Map<String, Object> out = new HashMap<>();
        out.put("message", "호출 수락을 취소했습니다.");
        out.put("data", StaffCallItemResponse.from(sc));
        return out;
    }

    @Transactional
    public Map<String, Object> complete(Long boothId, StaffCallCompleteRequest req) {
        if (req.getTableId() == null || req.getCartId() == null || req.getCallType() == null) {
            throw new IllegalArgumentException("table_id, cart_id, call_type은 필수입니다.");
        }

        StaffCall sc = staffCallRepository
                .findByTableCartCallTypeForUpdate(req.getTableId(), req.getCartId(), req.getCallType())
                .orElseThrow(() -> new IllegalArgumentException("해당 호출을 찾을 수 없습니다."));

        if (!boothId.equals(sc.getBoothId())) {
            throw new IllegalArgumentException("부스 정보가 일치하지 않습니다.");
        }

        if (sc.getStatus() != StaffCallStatus.ACCEPTED) {
            if (sc.getStatus() == StaffCallStatus.COMPLETED) {
                throw new StaffCallConflictException("이미 완료된 요청입니다.");
            }
            throw new StaffCallConflictException("수락된 호출만 완료 처리할 수 있습니다.");
        }

        sc.complete();

        publishRedis(sc, "staff_call_completed");
        try {
            staffCallWebSocketHandler.broadcastSnapshot(boothId,
                    staffCallQueryService.listForBooth(boothId, 50, 0));
            customerStaffCallWebSocketHandler.broadcastStatus(sc);
        } catch (Exception e) {
            log.error("[staffcall complete] 스냅샷 조회/WS 푸시 실패 — 완료는 반영됨 boothId={}", boothId, e);
        }

        Map<String, Object> out = new HashMap<>();
        out.put("message", "호출을 완료 처리했습니다.");
        out.put("data", StaffCallItemResponse.from(sc));
        return out;
    }

    /**
     * 무인증 고객이 생성 직후 staff_call을 삭제(취소)하는 API.
     * - subscribe_token으로만 권한 검증
     * - PENDING 상태만 삭제 가능 (ACCEPTED 이후는 충돌)
     */
    @Transactional
    public Map<String, Object> deleteByCustomer(StaffCallDeleteRequest req) {
        if (req == null || req.getStaffCallId() == null) {
            throw new IllegalArgumentException("staff_call_id는 필수입니다.");
        }
        Long staffCallId = req.getStaffCallId();
        String token = req.getSubscribeToken();
        if (token == null || token.isBlank()) {
            throw new IllegalArgumentException("subscribe_token은 필수입니다.");
        }
        if (!customerStaffCallWebSocketHandler.isValidSubscribeToken(staffCallId, token)) {
            throw new StaffCallConflictException("유효하지 않은 subscribe_token 입니다.");
        }

        StaffCall sc = staffCallRepository.findById(staffCallId)
                .orElseThrow(() -> new IllegalArgumentException("해당 호출을 찾을 수 없습니다."));

        if (sc.getStatus() != StaffCallStatus.PENDING) {
            throw new StaffCallConflictException("대기 중인 호출만 취소할 수 있습니다.");
        }

        Long boothId = sc.getBoothId();
        staffCallRepository.delete(sc);

        publishRedis(sc, "staff_call_deleted");
        try {
            staffCallWebSocketHandler.broadcastSnapshot(boothId,
                    staffCallQueryService.listForBooth(boothId, 50, 0));
            customerStaffCallWebSocketHandler.broadcastDeleted(staffCallId);
        } catch (Exception e) {
            log.error("[staffcall deleteByCustomer] 스냅샷 조회/WS 푸시 실패 — 삭제는 반영됨 boothId={}", boothId, e);
        }

        Map<String, Object> out = new HashMap<>();
        out.put("message", "호출을 취소했습니다.");
        out.put("data", Map.of("staff_call_id", staffCallId));
        return out;
    }

    @Transactional
    public Map<String, Object> emit(StaffCallEmitRequest req) {
        if (req.getTableId() == null || req.getCartId() == null || req.getCallType() == null || req.getCategory() == null) {
            throw new IllegalArgumentException("table_id, cart_id, call_type, category는 필수입니다.");
        }

        CartEntity cart = cartEntityRepository.findById(req.getCartId())
                .orElseThrow(() -> new IllegalArgumentException("카트를 찾을 수 없습니다."));

        TableUsageEntity usage = tableUsageEntityRepository.findById(cart.getTableUsageId())
                .orElseThrow(() -> new IllegalArgumentException("테이블 사용 정보를 찾을 수 없습니다."));

        if (!usage.getTableId().equals(req.getTableId())) {
            throw new IllegalArgumentException("카트와 테이블이 일치하지 않습니다.");
        }

        // 요청 body의 tableId가 부정확할 수 있으므로, cart->tableUsage으로 확정한 실제 tableId로 테이블을 조회한다.
        Long actualTableId = usage.getTableId();

        BoothTable table = boothTableRepository.findById(actualTableId)
                .orElseThrow(() -> new IllegalArgumentException("테이블을 찾을 수 없습니다."));
        Long boothId = table.getBoothId();

        if (!"AVAILABLE".equals(table.getStatus()) && !"IN_USE".equals(table.getStatus())) {
            throw new IllegalArgumentException("비활성 테이블에서는 호출할 수 없습니다.");
        }

        long activeDup = staffCallRepository.countByTableIdAndCartIdAndCallTypeAndStatusIn(
                actualTableId, req.getCartId(), req.getCallType(),
                List.of(StaffCallStatus.PENDING, StaffCallStatus.ACCEPTED));
        if (activeDup > 0) {
            throw new StaffCallConflictException("동일한 호출이 이미 진행 중입니다.");
        }

        int displayCartPrice = cartPayableAmountService.resolvePayableTotal(cart);

        StaffCall sc = StaffCall.builder()
                .boothId(boothId)
                .tableId(actualTableId)
                .tableUsageId(cart.getTableUsageId())
                .tableNum(table.getTableNum())
                .cartPrice(displayCartPrice)
                .cartId(req.getCartId())
                .callType(req.getCallType())
                .category(req.getCategory())
                .build();

        staffCallRepository.save(sc);

        String subscribeToken = customerStaffCallWebSocketHandler.issueSubscribeToken(sc.getId());

        publishRedis(sc, "staff_call_created");
        try {
            staffCallWebSocketHandler.broadcastSnapshot(boothId,
                    staffCallQueryService.listForBooth(boothId, 50, 0));
            customerStaffCallWebSocketHandler.broadcastStatus(sc);
        } catch (Exception e) {
            // 호출 생성/수락은 저장 트랜잭션에 포함된 비즈니스 결과이므로
            // WS 스냅샷 실패가 전체 요청을 500으로 만들지 않도록 예외를 삼킨다.
            log.error("[staffcall emit] 스냅샷 조회/WS 푸시 실패 — 호출 저장은 반영됨 boothId={}", boothId, e);
        }

        Map<String, Object> out = new HashMap<>();
        out.put("message", "직원 호출이 등록되었습니다.");
        out.put("data", StaffCallItemResponse.from(sc));
        out.put("subscribe_token", subscribeToken);
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
