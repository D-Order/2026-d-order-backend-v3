package com.example.spring.controller.staffcall;

import com.example.spring.dto.staffcall.request.StaffCallAcceptRequest;
import com.example.spring.dto.staffcall.request.StaffCallCancelRequest;
import com.example.spring.dto.staffcall.request.StaffCallCompleteRequest;
import com.example.spring.dto.staffcall.request.StaffCallDeleteRequest;
import com.example.spring.dto.staffcall.request.StaffCallEmitRequest;
import com.example.spring.dto.staffcall.request.StaffCallListRequest;
import com.example.spring.dto.staffcall.request.OrderCancelRequest;
import com.example.spring.dto.staffcall.response.StaffCallAcceptResponse;
import com.example.spring.security.ServerApiJwtFilter;
import com.example.spring.service.staffcall.StaffCallConflictException;
import com.example.spring.service.staffcall.OrderCancelService;
import com.example.spring.service.staffcall.StaffCallQueryService;
import com.example.spring.service.staffcall.StaffCallService;
import lombok.RequiredArgsConstructor;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;

import java.util.Map;
import jakarta.servlet.http.HttpServletRequest;

@RestController
@RequestMapping("/server")
@RequiredArgsConstructor
public class  StaffCallController {

    private final StaffCallQueryService staffCallQueryService;
    private final StaffCallService staffCallService;
    private final OrderCancelService orderCancelService;

    /**
     * 직원 호출 발생 — 경로를 {@code /staffcall/{boothId}} 보다 먼저 등록 (request가 boothId로 오인되지 않도록)
     */
    @PostMapping("/staffcall/request")
    public ResponseEntity<Map<String, Object>> emit(
            @RequestBody StaffCallEmitRequest body) {
        try {
            return ResponseEntity.ok(staffCallService.emit(body));
        } catch (StaffCallConflictException e) {
            return ResponseEntity.status(HttpStatus.CONFLICT).body(Map.of("message", e.getMessage()));
        } catch (IllegalArgumentException e) {
            return ResponseEntity.badRequest().body(Map.of("message", e.getMessage()));
        }
    }

    /**
     * 직원 호출 삭제(생성 직후 취소) — 무인증 고객용.
     * subscribe_token 검증 후, PENDING 상태의 staff_call만 삭제한다.
     */
    @PostMapping("/staffcall/delete")
    public ResponseEntity<Map<String, Object>> delete(
            @RequestBody StaffCallDeleteRequest body) {
        try {
            return ResponseEntity.ok(staffCallService.deleteByCustomer(body));
        } catch (StaffCallConflictException e) {
            return ResponseEntity.status(HttpStatus.CONFLICT).body(Map.of("message", e.getMessage()));
        } catch (IllegalArgumentException e) {
            return ResponseEntity.badRequest().body(Map.of("message", e.getMessage()));
        }
    }

    /**
     * POST /api/v3/spring/server/staffcall/{booth_id}
     * JWT의 booth_id와 경로가 일치해야 함 (은호님: JWT만 써도 되지만 스펙 경로 유지)
     */
    @PostMapping("/staffcall/{boothId}")
    public ResponseEntity<Map<String, Object>> list(
            @PathVariable Long boothId,
            @RequestBody(required = false) StaffCallListRequest body,
            HttpServletRequest request) {
        Long jwtBooth = (Long) request.getAttribute(ServerApiJwtFilter.ATTR_BOOTH_ID);
        if (jwtBooth == null || !jwtBooth.equals(boothId)) {
            return ResponseEntity.status(HttpStatus.FORBIDDEN)
                    .body(Map.of("message", "부스 정보가 일치하지 않습니다."));
        }
        StaffCallListRequest req = body != null ? body : new StaffCallListRequest();
        return ResponseEntity.ok(staffCallQueryService.listForBooth(boothId, req.getLimit(), req.getOffset()));
    }

    /**
     * POST /api/v3/spring/server/accept
     */
    @PostMapping("/accept")
    public ResponseEntity<Map<String, Object>> accept(
            @RequestBody StaffCallAcceptRequest body,
            HttpServletRequest request) {
        try {
            Long boothId = (Long) request.getAttribute(ServerApiJwtFilter.ATTR_BOOTH_ID);
            String accessToken = (String) request.getAttribute("ACCESS_TOKEN");
            String sessionId = (String) request.getAttribute(ServerApiJwtFilter.ATTR_SESSION_ID);
            StaffCallAcceptResponse data = staffCallService.accept(boothId, accessToken, sessionId, body);
            return ResponseEntity.ok(Map.of(
                    "message", "호출을 수락했습니다.",
                    "data", data
            ));
        } catch (StaffCallConflictException e) {
            return ResponseEntity.status(HttpStatus.CONFLICT).body(Map.of("message", e.getMessage()));
        } catch (IllegalArgumentException e) {
            return ResponseEntity.badRequest().body(Map.of("message", e.getMessage()));
        }
    }

    /**
     * POST /api/v3/spring/server/staffcall/complete
     * 수락된 호출을 완료 처리 → Redis로 Django에 결제확인 이벤트 발행
     */
    @PostMapping("/staffcall/complete")
    public ResponseEntity<Map<String, Object>> complete(
            @RequestBody StaffCallCompleteRequest body,
            HttpServletRequest request) {
        try {
            Long boothId = (Long) request.getAttribute(ServerApiJwtFilter.ATTR_BOOTH_ID);
            return ResponseEntity.ok(staffCallService.complete(boothId, body));
        } catch (StaffCallConflictException e) {
            return ResponseEntity.status(HttpStatus.CONFLICT).body(Map.of("message", e.getMessage()));
        } catch (IllegalArgumentException e) {
            return ResponseEntity.badRequest().body(Map.of("message", e.getMessage()));
        }
    }

    /**
     * POST /api/v3/spring/server/staffcall/cancel
     */
    @PostMapping("/staffcall/cancel")
    public ResponseEntity<Map<String, Object>> cancelAccept(
            @RequestBody StaffCallCancelRequest body,
            HttpServletRequest request) {
        try {
            Long boothId = (Long) request.getAttribute(ServerApiJwtFilter.ATTR_BOOTH_ID);
            String accessToken = (String) request.getAttribute("ACCESS_TOKEN");
            return ResponseEntity.ok(staffCallService.cancelAccept(boothId, accessToken, body));
        } catch (StaffCallConflictException e) {
            return ResponseEntity.status(HttpStatus.CONFLICT).body(Map.of("message", e.getMessage()));
        } catch (IllegalArgumentException e) {
            return ResponseEntity.badRequest().body(Map.of("message", e.getMessage()));
        }
    }

    /**
     * 주문 취소(직원/운영) 단일 API.
     * - Django 결제취소(payment-cancel) 성공 시에만 staffcall을 삭제하고
     * - 마지막에 커스터머에게 DELETED를 1회 푸시한다.
     *
     * POST /api/v3/spring/server/order/cancel
     */
    @PostMapping("/order/cancel")
    public ResponseEntity<Map<String, Object>> cancelOrder(
            @RequestBody OrderCancelRequest body,
            HttpServletRequest request) {
        try {
            Long boothId = (Long) request.getAttribute(ServerApiJwtFilter.ATTR_BOOTH_ID);
            Long staffCallId = body != null ? body.getStaffCallId() : null;
            return ResponseEntity.ok(orderCancelService.cancelOrder(boothId, staffCallId));
        } catch (StaffCallConflictException e) {
            return ResponseEntity.status(HttpStatus.CONFLICT).body(Map.of("message", e.getMessage()));
        } catch (IllegalArgumentException e) {
            return ResponseEntity.badRequest().body(Map.of("message", e.getMessage()));
        }
    }
}
