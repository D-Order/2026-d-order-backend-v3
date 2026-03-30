package com.example.spring.controller.staffcall;

import com.example.spring.dto.staffcall.request.StaffCallAcceptRequest;
import com.example.spring.dto.staffcall.request.StaffCallEmitRequest;
import com.example.spring.dto.staffcall.request.StaffCallListRequest;
import com.example.spring.dto.staffcall.response.StaffCallAcceptResponse;
import com.example.spring.security.ServerApiJwtFilter;
import com.example.spring.service.staffcall.StaffCallConflictException;
import com.example.spring.service.staffcall.StaffCallQueryService;
import com.example.spring.service.staffcall.StaffCallService;
import jakarta.servlet.http.HttpServletRequest;
import lombok.RequiredArgsConstructor;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;

import java.util.Map;

@RestController
@RequestMapping("/server")
@RequiredArgsConstructor
public class StaffCallController {

    private final StaffCallQueryService staffCallQueryService;
    private final StaffCallService staffCallService;

    /**
     * 직원 호출 발생 — 경로를 {@code /staffcall/{boothId}} 보다 먼저 등록 (request가 boothId로 오인되지 않도록)
     */
    @PostMapping("/staffcall/request")
    public ResponseEntity<Map<String, Object>> emit(@RequestBody StaffCallEmitRequest body) {
        try {
            return ResponseEntity.ok(staffCallService.emit(body));
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
        String accessToken = (String) request.getAttribute("ACCESS_TOKEN");
        try {
            StaffCallAcceptResponse data = staffCallService.accept(body, accessToken);
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
}
