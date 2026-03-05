package com.example.spring.controller.serving;

import com.example.spring.domain.serving.ServingTask;
import com.example.spring.dto.serving.request.CatchCallRequest;
import com.example.spring.dto.serving.response.ServingTaskResponse;
import com.example.spring.service.serving.ServingTaskService;
import lombok.RequiredArgsConstructor;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;

import java.util.List;
import java.util.stream.Collectors;

@RestController
@RequestMapping("/serving") // Nginx에서 /api/v3/spring/ 제거 후 진입하는 기본 경로
@RequiredArgsConstructor
public class ServingTaskController {

    private final ServingTaskService servingTaskService;

    // 1. 부스 별 서빙 요청 목록 조회 (GET /serving/servingcall/{booth_id})
    @GetMapping("/servingcall/{boothId}")
    public ResponseEntity<List<ServingTaskResponse>> getPendingCalls(@PathVariable Long boothId) {
        List<ServingTask> tasks = servingTaskService.getPendingServingCalls(boothId);

        // Entity List를 Response DTO List로 변환
        List<ServingTaskResponse> response = tasks.stream()
                .map(ServingTaskResponse::from)
                .collect(Collectors.toList());

        return ResponseEntity.ok(response);
    }

    // 2. 서빙 요청 수락 (POST /serving/catchcall)
    @PostMapping("/catchcall")
    public ResponseEntity<String> catchCall(
            @RequestParam Long taskId,
            @RequestParam Long boothId,
            @RequestBody CatchCallRequest request) {

        servingTaskService.catchCall(taskId, boothId, request.getCatchedBy());
        return ResponseEntity.ok("서빙 요청이 수락되었습니다.");
    }

    // 3. 서빙 완료 (POST /serving/complete)
    @PostMapping("/complete")
    public ResponseEntity<String> completeCall(
            @RequestParam Long taskId,
            @RequestParam Long boothId) {

        servingTaskService.completeCall(taskId, boothId);
        return ResponseEntity.ok("서빙이 완료되었습니다.");
    }

    // 4. 서빙 수락 취소 (POST /serving/cancel)
    @PostMapping("/cancel")
    public ResponseEntity<String> cancelCall(
            @RequestParam Long taskId,
            @RequestParam Long boothId) {

        servingTaskService.cancelCall(taskId, boothId);
        return ResponseEntity.ok("서빙 수락이 취소되었습니다.");
    }
}