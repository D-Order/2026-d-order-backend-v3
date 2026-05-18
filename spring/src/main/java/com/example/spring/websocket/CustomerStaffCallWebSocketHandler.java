package com.example.spring.websocket;

import com.example.spring.domain.staffcall.StaffCall;
import com.example.spring.repository.staffcall.StaffCallRepository;
import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.data.redis.core.StringRedisTemplate;
import org.springframework.stereotype.Component;
import org.springframework.web.socket.CloseStatus;
import org.springframework.web.socket.TextMessage;
import org.springframework.web.socket.WebSocketSession;
import org.springframework.web.socket.handler.TextWebSocketHandler;

import java.io.IOException;
import java.security.SecureRandom;
import java.time.Duration;
import java.time.OffsetDateTime;
import java.util.Base64;
import java.util.HashMap;
import java.util.Map;
import java.util.Set;
import java.util.concurrent.ConcurrentHashMap;

/**
 * 커스터머(태블릿/웹)에서 특정 staff_call_id의 상태 변화를 구독하기 위한 WS.
 *
 * - 인증(쿠키/JWT) 없이 연결 가능해야 하므로, staff_call_id + subscribe_token으로 구독을 허용한다.
 * - 이후 ACCEPTED/PENDING 등 상태 변화가 발생하면 해당 staff_call_id 구독자에게 이벤트를 푸시한다.
 */
@Slf4j
@Component
@RequiredArgsConstructor
public class CustomerStaffCallWebSocketHandler extends TextWebSocketHandler {

    private static final String REDIS_SUBSCRIBE_TOKEN_KEY_PREFIX = "spring:staffcall:subscribe:";
    private static final Duration SUBSCRIBE_TOKEN_TTL = Duration.ofMinutes(30);
    private static final SecureRandom SECURE_RANDOM = new SecureRandom();

    private final StaffCallRepository staffCallRepository;
    private final ObjectMapper objectMapper;
    private final StringRedisTemplate redisTemplate;

    private final Map<Long, Set<WebSocketSession>> staffCallSessions = new ConcurrentHashMap<>();

    @Override
    public void afterConnectionEstablished(WebSocketSession session) {
        log.info("[customer staffcall ws] 연결 session={}", session.getId());
    }

    @Override
    public void afterConnectionClosed(WebSocketSession session, CloseStatus status) {
        for (Set<WebSocketSession> set : staffCallSessions.values()) {
            set.remove(session);
        }
    }

    @Override
    protected void handleTextMessage(WebSocketSession session, TextMessage message) throws Exception {
        JsonNode root = objectMapper.readTree(message.getPayload());
        String type = root.path("type").asText("");
        if ("PING".equalsIgnoreCase(type)) {
            sendHeartbeatPong(session);
            return;
        }
        if (!"SUBSCRIBE".equalsIgnoreCase(type)) {
            return;
        }

        long staffCallId = root.path("staff_call_id").asLong(0);
        String token = root.path("subscribe_token").asText("");
        if (staffCallId <= 0) {
            session.sendMessage(new TextMessage(objectMapper.writeValueAsString(Map.of(
                    "type", "ERROR",
                    "message", "staff_call_id가 필요합니다."
            ))));
            return;
        }
        if (token == null || token.isBlank()) {
            session.sendMessage(new TextMessage(objectMapper.writeValueAsString(Map.of(
                    "type", "ERROR",
                    "message", "subscribe_token이 필요합니다."
            ))));
            return;
        }

        StaffCall sc = staffCallRepository.findById(staffCallId).orElse(null);
        if (sc == null) {
            session.sendMessage(new TextMessage(objectMapper.writeValueAsString(Map.of(
                    "type", "ERROR",
                    "message", "구독할 수 없는 staff_call_id 입니다."
            ))));
            return;
        }

        String expected = getSubscribeToken(staffCallId);
        if (expected == null || !expected.equals(token)) {
            session.sendMessage(new TextMessage(objectMapper.writeValueAsString(Map.of(
                    "type", "ERROR",
                    "message", "유효하지 않은 subscribe_token 입니다."
            ))));
            return;
        }

        staffCallSessions.computeIfAbsent(staffCallId, k -> ConcurrentHashMap.newKeySet()).add(session);

        session.sendMessage(new TextMessage(objectMapper.writeValueAsString(Map.of(
                "type", "SUBSCRIBED",
                "staff_call_id", staffCallId
        ))));

        // 구독 직후 현재 상태를 즉시 내려준다 (커스터머는 이걸 보고 화면 전환 판단 가능)
        session.sendMessage(new TextMessage(objectMapper.writeValueAsString(statusEvent(sc))));
    }

    public void broadcastStatus(StaffCall sc) {
        Set<WebSocketSession> sessions = staffCallSessions.get(sc.getId());
        if (sessions == null || sessions.isEmpty()) return;

        try {
            String json = objectMapper.writeValueAsString(statusEvent(sc));
            TextMessage tm = new TextMessage(json);
            for (WebSocketSession s : sessions) {
                if (s.isOpen()) {
                    try {
                        s.sendMessage(tm);
                    } catch (IOException e) {
                        log.warn("[customer staffcall ws] 전송 실패 session={}", s.getId(), e);
                    }
                }
            }
        } catch (Exception e) {
            log.error("[customer staffcall ws] broadcast 실패 staffCallId={}", sc.getId(), e);
        }
    }

    public void broadcastDeleted(Long staffCallId) {
        Set<WebSocketSession> sessions = staffCallSessions.get(staffCallId);
        if (sessions == null || sessions.isEmpty()) return;

        try {
            String json = objectMapper.writeValueAsString(Map.of(
                    "type", "STAFF_CALL_STATUS",
                    "staff_call_id", staffCallId,
                    "status", "DELETED"
            ));
            TextMessage tm = new TextMessage(json);
            for (WebSocketSession s : sessions) {
                if (s.isOpen()) {
                    try {
                        s.sendMessage(tm);
                    } catch (IOException e) {
                        log.warn("[customer staffcall ws] 삭제 전송 실패 session={}", s.getId(), e);
                    }
                }
            }
        } catch (Exception e) {
            log.error("[customer staffcall ws] broadcastDeleted 실패 staffCallId={}", staffCallId, e);
        } finally {
            staffCallSessions.remove(staffCallId);
        }
    }

    private Map<String, Object> statusEvent(StaffCall sc) {
        Map<String, Object> out = new HashMap<>();
        out.put("type", "STAFF_CALL_STATUS");
        out.put("staff_call_id", sc.getId());
        out.put("status", sc.getStatus() != null ? sc.getStatus().name() : null);
        out.put("accepted_by", sc.getAcceptedBy());
        out.put("accepted_at", sc.getAcceptedAt());
        out.put("table_id", sc.getTableId());
        out.put("cart_id", sc.getCartId());
        out.put("call_type", sc.getCallType());
        return out;
    }

    /**
     * staff_call_id 기반 커스터머 구독 토큰을 발급한다.
     * (DB 인증 없이 구독할 수 있도록, 서버가 알고 있는 일회성/단기 토큰을 사용)
     */
    public String issueSubscribeToken(Long staffCallId) {
        byte[] bytes = new byte[24];
        SECURE_RANDOM.nextBytes(bytes);
        String token = Base64.getUrlEncoder().withoutPadding().encodeToString(bytes);
        redisTemplate.opsForValue().set(REDIS_SUBSCRIBE_TOKEN_KEY_PREFIX + staffCallId, token, SUBSCRIBE_TOKEN_TTL);
        return token;
    }

    public boolean isValidSubscribeToken(Long staffCallId, String token) {
        if (staffCallId == null || staffCallId <= 0) return false;
        if (token == null || token.isBlank()) return false;
        String expected = getSubscribeToken(staffCallId);
        return expected != null && expected.equals(token);
    }

    private String getSubscribeToken(Long staffCallId) {
        return redisTemplate.opsForValue().get(REDIS_SUBSCRIBE_TOKEN_KEY_PREFIX + staffCallId);
    }

    /** Django cart WS와 동일한 JSON 하트비트 응답 (연결 유지·유휴 끊김 완화). */
    private void sendHeartbeatPong(WebSocketSession session) throws IOException {
        Map<String, Object> body = new HashMap<>();
        body.put("type", "PONG");
        body.put("timestamp", OffsetDateTime.now().toString());
        body.put("message", "heartbeat");
        body.put("data", null);
        session.sendMessage(new TextMessage(objectMapper.writeValueAsString(body)));
    }
}

