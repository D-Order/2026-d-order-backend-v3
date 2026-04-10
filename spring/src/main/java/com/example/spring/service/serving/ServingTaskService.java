package com.example.spring.service.serving;

import com.example.spring.domain.serving.ServingStatus;
import com.example.spring.domain.serving.ServingTask;
import com.example.spring.dto.redis.ServingStatusMessageDto;
import com.example.spring.dto.serving.response.ServingTaskResponse;
import com.example.spring.repository.serving.ServingTaskRepository;
import com.example.spring.websocket.ServingWebSocketHandler;
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
        return servingTaskRepository.findByBoothIdAndStatusOrderByRequestedAtAsc(
                boothId,
                ServingStatus.SERVE_REQUESTED
        );
    }

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

            if (!task.getBoothId().equals(boothId)) {
                throw new IllegalStateException("해당 부스의 서빙 요청이 아닙니다.");
            }

            if (task.getStatus() != ServingStatus.SERVE_REQUESTED) {
                throw new IllegalStateException("이미 처리된 요청입니다.");
            }

            String actor = (catchedBy != null && !catchedBy.isEmpty()) ? catchedBy : "STAFF";
            task.acceptServing(actor);

            publishToDjango(boothId, "serving", task.getOrderItemId(), actor);
            webSocketHandler.broadcastEvent("CATCH_CALL", ServingTaskResponse.from(task));

        } finally {
            redisTemplate.delete(lockKey);
        }
    }

    @Transactional
    public void completeCall(Long taskId, Long boothId) {
        ServingTask task = servingTaskRepository.findById(taskId)
                .orElseThrow(() -> new IllegalArgumentException("존재하지 않는 서빙 요청입니다. taskId=" + taskId));

        if (!task.getBoothId().equals(boothId)) {
            throw new IllegalStateException("해당 부스의 서빙 요청이 아닙니다.");
        }

        task.completeServing();

        publishToDjango(boothId, "served", task.getOrderItemId(), null);
        webSocketHandler.broadcastEvent("COMPLETE_CALL", ServingTaskResponse.from(task));
    }

    @Transactional
    public void cancelCall(Long taskId, Long boothId) {
        ServingTask task = servingTaskRepository.findById(taskId)
                .orElseThrow(() -> new IllegalArgumentException("존재하지 않는 서빙 요청입니다. taskId=" + taskId));

        if (!task.getBoothId().equals(boothId)) {
            throw new IllegalStateException("해당 부스의 서빙 요청이 아닙니다.");
        }

        task.cancelServing();

        publishToDjango(boothId, "cooked", task.getOrderItemId(), null);
        webSocketHandler.broadcastEvent("CANCEL_CALL", ServingTaskResponse.from(task));
    }

    /**
     * Django -> Spring : 조리 완료 알림 수신 시 새 serving_task 생성
     */
    @Transactional
    public void createNewServingTask(Long boothId, Long orderItemId, String key) {
        ServingTask newTask = ServingTask.builder()
                .boothId(boothId)
                .orderItemId(orderItemId)
                .key(key)
                .build();

        servingTaskRepository.save(newTask);

        webSocketHandler.broadcastEvent("NEW_CALL", ServingTaskResponse.from(newTask));
        log.info("[새 서빙 요청 생성 및 브로드캐스트] boothId={}, orderItemId={}", boothId, orderItemId);
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