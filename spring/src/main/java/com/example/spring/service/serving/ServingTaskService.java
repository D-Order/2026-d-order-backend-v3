package com.example.spring.service.serving;

import com.example.spring.domain.serving.ServingStatus;
import com.example.spring.domain.serving.ServingTask;
import com.example.spring.dto.redis.ServingStatusMessageDto;
import com.example.spring.dto.serving.response.ServingFilterOptionsData;
import com.example.spring.dto.serving.response.ServingMenuFilterOption;
import com.example.spring.dto.serving.response.ServingTaskResponse;
import com.example.spring.repository.serving.ServingTaskRepository;
import com.example.spring.websocket.ServingWebSocketHandler;
import com.fasterxml.jackson.databind.ObjectMapper;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.data.redis.core.StringRedisTemplate;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.time.OffsetDateTime; // 🌟 LocalDateTime -> OffsetDateTime 으로 변경
import java.util.HashMap;
import java.util.List;
import java.util.Map;
import java.util.concurrent.TimeUnit;

@Slf4j
@Service
@RequiredArgsConstructor
public class ServingTaskService {

    private static final List<ServingStatus> ACTIVE_SERVING_STATUSES = List.of(
            ServingStatus.SERVE_REQUESTED,
            ServingStatus.SERVING
    );

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
    // 🌟 catchedBy 파라미터 삭제됨
    public void catchCall(Long taskId, Long boothId) {
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

            // 🌟 actor(catchedBy) 전달 제거
            task.acceptServing();

            // 🌟 publishToDjango 호출 시 파라미터 수정 (null 제외)
            publishToDjango(boothId, "serving", task.getOrderItemId());
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

        publishToDjango(boothId, "served", task.getOrderItemId());
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

        publishToDjango(boothId, "cooked", task.getOrderItemId());
        webSocketHandler.broadcastEvent("CANCEL_CALL", ServingTaskResponse.from(task));
    }

    /**
     * Django -> Spring : 조리 완료 알림 수신 시 새 serving_task 생성
     */
    @Transactional
    public void createNewServingTask(Long boothId, Long orderItemId, Integer tableNumber, String menuName, Integer quantity, String key) {
        boolean alreadyExists = servingTaskRepository
                .findFirstByBoothIdAndOrderItemIdAndStatusIn(
                        boothId,
                        orderItemId,
                        ACTIVE_SERVING_STATUSES
                )
                .isPresent();

        if (alreadyExists) {
            log.info("[서빙 요청 중복 무시] boothId={}, orderItemId={}", boothId, orderItemId);
            return;
        }

        ServingTask newTask = ServingTask.builder()
                .boothId(boothId)
                .orderItemId(orderItemId)
                .tableNumber(tableNumber)
                .menuName(menuName)
                .quantity(quantity)
                .key(key)
                .build();

        servingTaskRepository.save(newTask);

        webSocketHandler.broadcastEvent("NEW_CALL", ServingTaskResponse.from(newTask));
        log.info("[새 서빙 요청 생성 및 브로드캐스트] boothId={}, orderItemId={}", boothId, orderItemId);
    }



    @Transactional(readOnly = true)
    public ServingFilterOptionsData getFilterOptions(Long boothId) {
        List<String> menuNames = servingTaskRepository
                .findDistinctMenuNamesByBoothIdAndStatus(boothId, ServingStatus.SERVE_REQUESTED);

        List<ServingMenuFilterOption> menus = menuNames.stream()
                .map(menuName -> new ServingMenuFilterOption(menuName, menuName))
                .toList();

        List<Integer> tables = servingTaskRepository
                .findDistinctTableNumbersByBoothIdAndStatus(boothId, ServingStatus.SERVE_REQUESTED);

        return new ServingFilterOptionsData(menus, tables);
    }

    @Transactional
    public void removeTasksByOrderItemId(Long boothId, Long orderItemId, String reason) {
        long deletedCount = servingTaskRepository.deleteByBoothIdAndOrderItemIdAndStatusIn(
                boothId,
                orderItemId,
                ACTIVE_SERVING_STATUSES
        );
        if (deletedCount > 0) {
            webSocketHandler.broadcastEvent(
                    "REMOVE_CALL",
                    buildRemoveCallPayload(boothId, reason, deletedCount, orderItemId, null)
            );
        }
        log.info("[서빙 요청 삭제] boothId={}, orderItemId={}, reason={}, deletedCount={}", boothId, orderItemId, reason, deletedCount);
    }

    @Transactional
    public void removeTasksByTableNumber(Long boothId, Integer tableNumber, String reason) {
        long deletedCount = servingTaskRepository.deleteByBoothIdAndTableNumberAndStatusIn(
                boothId,
                tableNumber,
                ACTIVE_SERVING_STATUSES
        );
        if (deletedCount > 0) {
            webSocketHandler.broadcastEvent(
                    "REMOVE_CALL",
                    buildRemoveCallPayload(boothId, reason, deletedCount, null, tableNumber)
            );
        }
        log.info("[테이블 기준 서빙 요청 삭제] boothId={}, tableNumber={}, reason={}, deletedCount={}", boothId, tableNumber, reason, deletedCount);
    }

    private Map<String, Object> buildRemoveCallPayload(
            Long boothId,
            String reason,
            long deletedCount,
            Long orderItemId,
            Integer tableNumber
    ) {
        Map<String, Object> payload = new HashMap<>();
        payload.put("boothId", boothId);
        payload.put("reason", reason);
        payload.put("deletedCount", deletedCount);
        if (orderItemId != null) {
            payload.put("orderItemId", orderItemId);
        }
        if (tableNumber != null) {
            payload.put("tableNumber", tableNumber);
        }
        return payload;
    }

    // 🌟 catchedBy 파라미터 삭제
    private void publishToDjango(Long boothId, String status, Long orderItemId) {
        try {
            ServingStatusMessageDto messageDto = ServingStatusMessageDto.builder()
                    .orderItemId(orderItemId)
                    .status(status)
                    // 🌟 OffsetDateTime 적용
                    .pushedAt(OffsetDateTime.now())
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