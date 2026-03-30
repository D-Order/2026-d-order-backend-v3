package com.example.spring.service.serving;

import com.example.spring.domain.serving.ServingStatus;
import com.example.spring.domain.serving.ServingTask;
import com.example.spring.dto.redis.ServingStatusMessageDto;
import com.example.spring.repository.serving.ServingTaskRepository;
import com.fasterxml.jackson.databind.ObjectMapper;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.data.redis.core.StringRedisTemplate;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.time.LocalDateTime;
import java.util.List;

@Slf4j
@Service
@RequiredArgsConstructor
public class ServingTaskService {

    private final ServingTaskRepository servingTaskRepository;
    private final StringRedisTemplate redisTemplate;
    private final ObjectMapper objectMapper;

    @Transactional(readOnly = true)
    public List<ServingTask> getPendingServingCalls(Long boothId) {
        /**
         * 현재 구조상 boothId로 serving_task를 필터링할 수 있는 컬럼이 없으므로
         * 우선 status 기준으로만 조회합니다.
         * 추후 boothId 필터링 구조가 필요하면 serving_task에 booth 정보가 있어야 합니다.
         */
        return servingTaskRepository.findByStatusOrderByRequestedAtAsc(ServingStatus.SERVE_REQUESTED);
    }

    @Transactional
    public void catchCall(Long taskId, Long boothId, String catchedBy) {
        ServingTask task = servingTaskRepository.findById(taskId)
                .orElseThrow(() -> new IllegalArgumentException("존재하지 않는 서빙 요청입니다. taskId=" + taskId));

        task.acceptServing(catchedBy);

        publishToDjango(boothId, "serving", task.getOrderItemId(), catchedBy);
    }

    @Transactional
    public void completeCall(Long taskId, Long boothId) {
        ServingTask task = servingTaskRepository.findById(taskId)
                .orElseThrow(() -> new IllegalArgumentException("존재하지 않는 서빙 요청입니다. taskId=" + taskId));

        task.completeServing();

        publishToDjango(boothId, "served", task.getOrderItemId(), null);
    }

    @Transactional
    public void cancelCall(Long taskId, Long boothId) {
        ServingTask task = servingTaskRepository.findById(taskId)
                .orElseThrow(() -> new IllegalArgumentException("존재하지 않는 서빙 요청입니다. taskId=" + taskId));

        task.cancelServing();

        publishToDjango(boothId, "cooked", task.getOrderItemId(), null);
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