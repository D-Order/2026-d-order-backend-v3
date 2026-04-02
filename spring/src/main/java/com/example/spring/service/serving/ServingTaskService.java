package com.example.spring.service.serving;

import com.example.spring.websocket.ServingWebSocketHandler;
import com.example.spring.domain.serving.ServingStatus;
import com.example.spring.domain.serving.ServingTask;
import com.example.spring.dto.redis.ServingStatusMessageDto;
import com.example.spring.dto.serving.response.ServingTaskResponse; // 🌟 이 부분이 추가되었습니다!
import com.example.spring.repository.serving.ServingTaskRepository;
import com.fasterxml.jackson.databind.ObjectMapper;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.data.redis.core.StringRedisTemplate;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.time.LocalDateTime;
import java.util.List;
import java.util.concurrent.TimeUnit;

@Slf4j
@Service
@RequiredArgsConstructor
public class ServingTaskService {

    private final ServingTaskRepository servingTaskRepository;
    private final StringRedisTemplate redisTemplate;
    private final ObjectMapper objectMapper;
    private final ServingWebSocketHandler webSocketHandler;

    @Transactional(readOnly = true)
    public List<ServingTask> getPendingServingCalls(Long boothId) {
        return servingTaskRepository.findByStatusOrderByRequestedAtAsc(ServingStatus.SERVE_REQUESTED);
    }

    // 🌟 수정됨: 서빙 수락 (Redis 선착순 락 적용)
    @Transactional
    public void catchCall(Long taskId, Long boothId, String catchedBy) {
        String lockKey = "lock:serving_task:" + taskId;
        Boolean isAcquired = redisTemplate.opsForValue()
                .setIfAbsent(lockKey, "locked", 5, TimeUnit.SECONDS);

        if (Boolean.FALSE.equals(isAcquired)) {
            throw new IllegalStateException("이미 다른 직원이 수락한 요청입니다.");
        }

        try {
            ServingTask task = servingTaskRepository.findById(taskId)
                    .orElseThrow(() -> new IllegalArgumentException("존재하지 않는 서빙 요청입니다. taskId=" + taskId));

            if (task.getStatus() != ServingStatus.SERVE_REQUESTED) {
                throw new IllegalStateException("이미 처리된 요청입니다.");
            }

            String actor = (catchedBy != null && !catchedBy.isEmpty()) ? catchedBy : "STAFF";
            task.acceptServing(actor);

            // 1. 장고 측으로 Redis 메시지 발행
            publishToDjango(boothId, "serving", task.getOrderItemId(), actor);

            // 2. 🌟 프론트엔드로 웹소켓 브로드캐스트 (CATCH_CALL 이벤트)
            webSocketHandler.broadcastEvent("CATCH_CALL", ServingTaskResponse.from(task));

        } finally {
            redisTemplate.delete(lockKey);
        }
    }

    @Transactional
    public void completeCall(Long taskId, Long boothId) {
        ServingTask task = servingTaskRepository.findById(taskId).orElseThrow();
        task.completeServing();

        publishToDjango(boothId, "served", task.getOrderItemId(), null);

        // 🌟 프론트엔드로 웹소켓 브로드캐스트 (COMPLETE_CALL 이벤트)
        webSocketHandler.broadcastEvent("COMPLETE_CALL", ServingTaskResponse.from(task));
    }

    @Transactional
    public void cancelCall(Long taskId, Long boothId) {
        ServingTask task = servingTaskRepository.findById(taskId).orElseThrow();
        task.cancelServing();

        publishToDjango(boothId, "cooked", task.getOrderItemId(), null);

        // 🌟 프론트엔드로 웹소켓 브로드캐스트 (CANCEL_CALL 이벤트)
        webSocketHandler.broadcastEvent("CANCEL_CALL", ServingTaskResponse.from(task));
    }

    // 장고(Django) -> 스프링(Spring) : 새 조리 완료 알림이 왔을 때 호출될 메서드
    @Transactional
    public void createNewServingTask(Long orderItemId, String key) {
        // 1. 새 태스크 생성 및 저장
        ServingTask newTask = ServingTask.builder()
                .orderItemId(orderItemId)
                .key(key)
                .build();
        servingTaskRepository.save(newTask);

        // 2. 🌟 프론트엔드로 웹소켓 브로드캐스트 (NEW_CALL 이벤트)
        webSocketHandler.broadcastEvent("NEW_CALL", ServingTaskResponse.from(newTask));
        log.info("[새 서빙 요청 생성 및 브로드캐스트] orderItemId: {}", orderItemId);
    }

    private void publishToDjango(Long boothId, String status, Long orderItemId, String catchedBy) {
        try {
            ServingStatusMessageDto messageDto = ServingStatusMessageDto.builder()
                    .orderItemId(orderItemId)
                    .status(status)
                    .catchedBy(catchedBy)
                    .pushedAt(LocalDateTime.now())
                    .build();

            String jsonMessage = objectMapper.writeValueAsString(messageDto);
            String channel = "spring:booth:" + boothId + ":order:" + status;

            redisTemplate.convertAndSend(channel, jsonMessage);
            log.info("[Redis 발행 완료] 채널: {}, 데이터: {}", channel, jsonMessage);

        } catch (Exception e) {
            log.error("[Redis 발행 실패] boothId={}, status={}, orderItemId={}", boothId, status, orderItemId, e);
        }
    }
}