package com.example.spring.controller.serving;

import com.example.spring.domain.serving.ServingTask;
import com.example.spring.dto.serving.request.CatchCallRequest;
import com.example.spring.dto.serving.response.ServingTaskResponse;
import com.example.spring.service.serving.ServingTaskService;
import lombok.RequiredArgsConstructor;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;

import java.util.List;
import java.util.stream.Collectors;

@RestController
@RequestMapping("/serving")
@RequiredArgsConstructor
public class ServingTaskController {

    private final ServingTaskService servingTaskService;

    @GetMapping("/servingcall/{boothId}")
    public ResponseEntity<List<ServingTaskResponse>> getPendingCalls(@PathVariable Long boothId) {
        List<ServingTask> tasks = servingTaskService.getPendingServingCalls(boothId);
        List<ServingTaskResponse> response = tasks.stream()
                .map(ServingTaskResponse::from)
                .collect(Collectors.toList());
        return ResponseEntity.ok(response);
    }

    @PostMapping("/catchcall")
    public ResponseEntity<String> catchCall(
            @RequestParam Long taskId,
            @RequestParam Long boothId,
            @RequestBody(required = false) CatchCallRequest request) { // 🌟 프론트에서 Body를 안 보낼 경우 방어

        String catchedBy = (request != null && request.getCatchedBy() != null) ? request.getCatchedBy() : "STAFF";
        servingTaskService.catchCall(taskId, boothId, catchedBy);
        return ResponseEntity.ok("서빙 요청이 수락되었습니다.");
    }

    @PostMapping("/complete")
    public ResponseEntity<String> completeCall(
            @RequestParam Long taskId,
            @RequestParam Long boothId) {
        servingTaskService.completeCall(taskId, boothId);
        return ResponseEntity.ok("서빙이 완료되었습니다.");
    }

    @PostMapping("/cancel")
    public ResponseEntity<String> cancelCall(
            @RequestParam Long taskId,
            @RequestParam Long boothId) {
        servingTaskService.cancelCall(taskId, boothId);
        return ResponseEntity.ok("서빙 수락이 취소되었습니다.");
    }

    // =========================================================================
    // 🌟 추가된 부분: Service에서 던진 예외를 프론트엔드 친화적인 HTTP 상태 코드로 변환
    // =========================================================================

    @ExceptionHandler(IllegalStateException.class)
    public ResponseEntity<String> handleIllegalStateException(IllegalStateException e) {
        // 동시성 문제(이미 누가 수락함) 또는 상태 불일치 시 409 Conflict 반환
        return ResponseEntity.status(HttpStatus.CONFLICT).body(e.getMessage());
    }

    @ExceptionHandler(IllegalArgumentException.class)
    public ResponseEntity<String> handleIllegalArgumentException(IllegalArgumentException e) {
        // 잘못된 taskId 등 존재하지 않는 데이터 접근 시 400 Bad Request 반환
        return ResponseEntity.status(HttpStatus.BAD_REQUEST).body(e.getMessage());
    }
}