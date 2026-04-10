package com.example.spring.controller.serving;

import com.example.spring.domain.serving.ServingTask;
import com.example.spring.dto.serving.response.ServingTaskResponse;
import com.example.spring.security.ServerApiJwtFilter;
import com.example.spring.service.serving.ServingTaskService;
import jakarta.servlet.http.HttpServletRequest;
import lombok.RequiredArgsConstructor;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;

import java.util.List;

@RestController
@RequestMapping("/serving")
@RequiredArgsConstructor
public class ServingTaskController {

    private final ServingTaskService servingTaskService;

    /**
     * 신규 운영자용 API
     * booth_id를 프론트에서 넘기지 않고 JWT 기준으로 조회
     * GET /api/v3/spring/serving/servingcall
     */
    @GetMapping("/servingcall")
    public ResponseEntity<List<ServingTaskResponse>> getMyPendingCalls(HttpServletRequest request) {
        Long boothId = (Long) request.getAttribute(ServerApiJwtFilter.ATTR_BOOTH_ID);

        if (boothId == null) {
            return ResponseEntity.status(HttpStatus.UNAUTHORIZED).build();
        }

        List<ServingTask> tasks = servingTaskService.getPendingServingCalls(boothId);
        List<ServingTaskResponse> response = tasks.stream()
                .map(ServingTaskResponse::from)
                .toList();

        return ResponseEntity.ok(response);
    }

    /**
     * 기존 경로 기반 API는 호환성 유지용
     * 필요 없으면 추후 제거 가능
     */
    @GetMapping("/servingcall/{boothId}")
    public ResponseEntity<List<ServingTaskResponse>> getPendingCalls(
            @PathVariable Long boothId,
            HttpServletRequest request
    ) {
        Long jwtBooth = (Long) request.getAttribute(ServerApiJwtFilter.ATTR_BOOTH_ID);

        if (jwtBooth == null || !jwtBooth.equals(boothId)) {
            return ResponseEntity.status(HttpStatus.FORBIDDEN).build();
        }

        List<ServingTask> tasks = servingTaskService.getPendingServingCalls(boothId);
        List<ServingTaskResponse> response = tasks.stream()
                .map(ServingTaskResponse::from)
                .toList();

        return ResponseEntity.ok(response);
    }

    @PostMapping("/catchcall")
    public ResponseEntity<String> catchCall(
            @RequestParam Long taskId,
            HttpServletRequest httpRequest // 🌟 @RequestBody CatchCallRequest 제거됨
    ) {
        Long boothId = (Long) httpRequest.getAttribute(ServerApiJwtFilter.ATTR_BOOTH_ID);

        if (boothId == null) {
            return ResponseEntity.status(HttpStatus.UNAUTHORIZED).body("인증 정보가 없습니다.");
        }

        // 🌟 3번째 인자(catchedBy) 제거됨
        servingTaskService.catchCall(taskId, boothId);
        return ResponseEntity.ok("서빙 요청이 수락되었습니다.");
    }

    @PostMapping("/complete")
    public ResponseEntity<String> completeCall(
            @RequestParam Long taskId,
            HttpServletRequest httpRequest
    ) {
        Long boothId = (Long) httpRequest.getAttribute(ServerApiJwtFilter.ATTR_BOOTH_ID);

        if (boothId == null) {
            return ResponseEntity.status(HttpStatus.UNAUTHORIZED).body("인증 정보가 없습니다.");
        }

        servingTaskService.completeCall(taskId, boothId);
        return ResponseEntity.ok("서빙이 완료되었습니다.");
    }

    @PostMapping("/cancel")
    public ResponseEntity<String> cancelCall(
            @RequestParam Long taskId,
            HttpServletRequest httpRequest
    ) {
        Long boothId = (Long) httpRequest.getAttribute(ServerApiJwtFilter.ATTR_BOOTH_ID);

        if (boothId == null) {
            return ResponseEntity.status(HttpStatus.UNAUTHORIZED).body("인증 정보가 없습니다.");
        }

        servingTaskService.cancelCall(taskId, boothId);
        return ResponseEntity.ok("서빙 수락이 취소되었습니다.");
    }
}