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
    private final StringRedisTemplate redisTemplate; // Redis 발행을 위한 내장 템플릿
    private final ObjectMapper objectMapper;

    // 1. 부스별 서빙 요청 리스트 조회
    @Transactional(readOnly = true)
    public List<ServingTask> getPendingServingCalls(Long boothId) {
        // TODO: 향후 boothId 기준으로 필터링하는 쿼리로 고도화 필요
        return servingTaskRepository.findAllByStatus(ServingStatus.SERVE_REQUESTED);
    }

    // 2. 서빙 수락 (Catch)
    @Transactional
    public void catchCall(Long taskId, Long boothId, String catchedBy) {
        ServingTask task = servingTaskRepository.findById(taskId)
                .orElseThrow(() -> new IllegalArgumentException("존재하지 않는 서빙 요청입니다."));

        task.acceptServing(catchedBy); // 상태 변경 (SERVING)

        // 장고로 상태 변경 메시지 발행
        publishToDjango(boothId, "serving", task.getOrderItem().getId(), catchedBy);
    }

    // 3. 서빙 완료
    @Transactional
    public void completeCall(Long taskId, Long boothId) {
        ServingTask task = servingTaskRepository.findById(taskId).orElseThrow();
        task.completeServing(); // 상태 변경 (SERVED)

        publishToDjango(boothId, "served", task.getOrderItem().getId(), null);
    }

    // 4. 서빙 수락 취소
    @Transactional
    public void cancelCall(Long taskId, Long boothId) {
        ServingTask task = servingTaskRepository.findById(taskId).orElseThrow();
        task.cancelServing(); // 상태 변경 (SERVE_REQUESTED 롤백)

        // 장고 측 OrderItem 상태도 다시 cooked로 롤백
        publishToDjango(boothId, "cooked", task.getOrderItem().getId(), null);
    }

    // 장고가 구독 중인 채널로 Redis 메시지 발행
    private void publishToDjango(Long boothId, String status, Long orderItemId, String catchedBy) {
        try {
            ServingStatusMessageDto messageDto = ServingStatusMessageDto.builder()
                    .orderItemId(orderItemId)
                    .status(status)
                    .catchedBy(catchedBy)
                    .pushedAt(LocalDateTime.now())
                    .build();

            // 객체를 JSON 문자열로 변환
            String jsonMessage = objectMapper.writeValueAsString(messageDto);

            // 이해는 못했으나.. 발행용 채널명 (spring: 접두사는 Nginx나 Redis 설정에서 안 붙는다면 여기서 직접 붙여야 할 수 있으나 명세서대로 "spring:" 포함)
            String channel = "spring:booth:" + boothId + ":order:" + status;

            redisTemplate.convertAndSend(channel, jsonMessage);
            log.info("[Redis 발행 완료] 채널: {}, 데이터: {}", channel, jsonMessage);

        } catch (Exception e) {
            log.error("[Redis 발행 실패]", e);
        }
    }
}