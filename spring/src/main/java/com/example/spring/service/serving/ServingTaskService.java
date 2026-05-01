package com.example.spring.service.serving;

import com.example.spring.config.DjangoApiUtil;
import com.example.spring.domain.serving.ServingStatus;
import com.example.spring.domain.serving.ServingTask;
import com.example.spring.dto.redis.ServingStatusMessageDto;
import com.example.spring.dto.serving.django.DjangoAdminMenuListResponse;
import com.example.spring.dto.serving.django.DjangoBoothMypageResponse;
import com.example.spring.dto.serving.response.ServingFilterOptionsData;
import com.example.spring.dto.serving.response.ServingMenuFilterOption;
import com.example.spring.dto.serving.response.ServingTaskResponse;
import com.example.spring.repository.serving.ServingTaskRepository;
import com.example.spring.websocket.ServingWebSocketHandler;
import com.fasterxml.jackson.databind.ObjectMapper;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.data.redis.core.StringRedisTemplate;
import org.springframework.http.*;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
import org.springframework.web.client.HttpClientErrorException;
import org.springframework.web.client.RestTemplate;

import java.time.OffsetDateTime;
import java.util.ArrayList;
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
    private final RestTemplate restTemplate;

    @Value("${django.api.base-url}")
    private String djangoApiBaseUrl;

    public static class DjangoApiException extends RuntimeException {
        private final HttpStatus status;
        private final String responseBody;

        public DjangoApiException(HttpStatus status, String responseBody) {
            super("Django API Error: " + status);
            this.status = status;
            this.responseBody = responseBody;
        }

        public HttpStatus getStatus() { return status; }
        public String getResponseBody() { return responseBody; }
    }

    @Transactional(readOnly = true)
    public List<ServingTask> getPendingServingCalls(Long boothId) {
        return servingTaskRepository.findByBoothIdAndStatusOrderByRequestedAtAsc(
                boothId,
                ServingStatus.SERVE_REQUESTED
        );
    }

    @Transactional(readOnly = true)
    public ServingFilterOptionsData getFilterOptions(Long boothId, String accessToken) {
        DjangoAdminMenuListResponse menuListResponse = fetchDjangoMenuList(accessToken);
        DjangoBoothMypageResponse mypageResponse = fetchDjangoBoothMypage(accessToken);

        List<ServingMenuFilterOption> menus = new ArrayList<>();
        List<DjangoAdminMenuListResponse.MenuItem> menuItems = menuListResponse != null ? menuListResponse.getData() : null;
        if (menuItems != null) {
            for (DjangoAdminMenuListResponse.MenuItem item : menuItems) {
                if (item == null || item.getId() == null || item.getName() == null) {
                    continue;
                }
                menus.add(new ServingMenuFilterOption(item.getId(), item.getName()));
            }
        }

        Integer tableCount = 0;
        if (mypageResponse != null && mypageResponse.getData() != null && mypageResponse.getData().getTableMaxCnt() != null) {
            tableCount = mypageResponse.getData().getTableMaxCnt();
        }

        List<Integer> tables = new ArrayList<>();
        for (int i = 1; i <= tableCount; i++) {
            tables.add(i);
        }

        return new ServingFilterOptionsData(menus, tableCount, tables);
    }

    private DjangoAdminMenuListResponse fetchDjangoMenuList(String accessToken) {
        String url = djangoApiBaseUrl + "/api/v3/django/booth/menu-list/";
        HttpEntity<Void> requestEntity = new HttpEntity<>(buildDjangoAuthHeaders(accessToken));

        try {
            ResponseEntity<DjangoAdminMenuListResponse> response = restTemplate.exchange(
                    url,
                    HttpMethod.GET,
                    requestEntity,
                    DjangoAdminMenuListResponse.class
            );
            return response.getBody();
        } catch (HttpClientErrorException e) {
            throw new DjangoApiException(HttpStatus.valueOf(e.getStatusCode().value()), e.getResponseBodyAsString());
        }
    }

    private DjangoBoothMypageResponse fetchDjangoBoothMypage(String accessToken) {
        String url = djangoApiBaseUrl + "/api/v3/django/booth/mypage/";
        HttpEntity<Void> requestEntity = new HttpEntity<>(buildDjangoAuthHeaders(accessToken));

        try {
            ResponseEntity<DjangoBoothMypageResponse> response = restTemplate.exchange(
                    url,
                    HttpMethod.GET,
                    requestEntity,
                    DjangoBoothMypageResponse.class
            );
            return response.getBody();
        } catch (HttpClientErrorException e) {
            throw new DjangoApiException(HttpStatus.valueOf(e.getStatusCode().value()), e.getResponseBodyAsString());
        }
    }

    private HttpHeaders buildDjangoAuthHeaders(String accessToken) {
        Map<String, String> csrfData = DjangoApiUtil.getCsrfToken(restTemplate, djangoApiBaseUrl);

        HttpHeaders headers = new HttpHeaders();
        headers.setAccept(List.of(MediaType.APPLICATION_JSON));
        if (csrfData.get("csrfToken") != null) {
            headers.set("X-CSRFToken", csrfData.get("csrfToken"));
        }

        StringBuilder cookieBuilder = new StringBuilder();
        if (csrfData.get("csrfCookie") != null) {
            cookieBuilder.append(csrfData.get("csrfCookie"));
        }
        if (accessToken != null) {
            if (cookieBuilder.length() > 0) {
                cookieBuilder.append("; ");
            }
            cookieBuilder.append("access_token=").append(accessToken);
        }
        if (cookieBuilder.length() > 0) {
            headers.set(HttpHeaders.COOKIE, cookieBuilder.toString());
        }

        return headers;
    }

    @Transactional
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

            task.acceptServing();

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

    @Transactional
    public void createNewServingTask(Long boothId, Long orderItemId, Integer tableNumber, Long menuId, String menuName, Integer quantity, String key) {
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
                .menuId(menuId)
                .menuName(menuName)
                .quantity(quantity)
                .key(key)
                .build();

        servingTaskRepository.save(newTask);

        webSocketHandler.broadcastEvent("NEW_CALL", ServingTaskResponse.from(newTask));
        log.info("[새 서빙 요청 생성 및 브로드캐스트] boothId={}, orderItemId={}", boothId, orderItemId);
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

    private void publishToDjango(Long boothId, String status, Long orderItemId) {
        try {
            ServingStatusMessageDto messageDto = ServingStatusMessageDto.builder()
                    .orderItemId(orderItemId)
                    .status(status)
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