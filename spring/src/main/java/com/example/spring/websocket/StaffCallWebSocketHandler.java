package com.example.spring.websocket;

import com.example.spring.service.staffcall.StaffCallQueryService;
import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.stereotype.Component;
import org.springframework.web.socket.CloseStatus;
import org.springframework.web.socket.TextMessage;
import org.springframework.web.socket.WebSocketSession;
import org.springframework.web.socket.handler.TextWebSocketHandler;

import java.io.IOException;
import java.util.HashMap;
import java.util.Map;
import java.util.Set;
import java.util.concurrent.ConcurrentHashMap;

import static com.example.spring.config.StaffCallHandshakeInterceptor.ATTR_BOOTH_ID;

/**
 * 부스 단위 직원 호출 목록 — LIST 요청 및 서버 푸시(STAFF_CALL_SNAPSHOT)
 */
@Slf4j
@Component
@RequiredArgsConstructor
public class StaffCallWebSocketHandler extends TextWebSocketHandler {

    private final StaffCallQueryService staffCallQueryService;
    private final ObjectMapper objectMapper;

    private final Map<Long, Set<WebSocketSession>> boothSessions = new ConcurrentHashMap<>();

    @Override
    public void afterConnectionEstablished(WebSocketSession session) {
        Long boothId = (Long) session.getAttributes().get(ATTR_BOOTH_ID);
        if (boothId == null) {
            try {
                session.close(CloseStatus.NOT_ACCEPTABLE);
            } catch (IOException ignored) {
            }
            return;
        }
        boothSessions.computeIfAbsent(boothId, k -> ConcurrentHashMap.newKeySet()).add(session);
        log.info("[staffcall ws] 연결 boothId={}, session={}", boothId, session.getId());
    }

    @Override
    public void afterConnectionClosed(WebSocketSession session, CloseStatus status) {
        Long boothId = (Long) session.getAttributes().get(ATTR_BOOTH_ID);
        if (boothId != null) {
            Set<WebSocketSession> set = boothSessions.get(boothId);
            if (set != null) {
                set.remove(session);
                if (set.isEmpty()) {
                    boothSessions.remove(boothId);
                }
            }
        }
    }

    @Override
    protected void handleTextMessage(WebSocketSession session, TextMessage message) throws Exception {
        Long boothId = (Long) session.getAttributes().get(ATTR_BOOTH_ID);
        if (boothId == null) {
            return;
        }
        JsonNode root = objectMapper.readTree(message.getPayload());
        String type = root.path("type").asText("");
        if (!"LIST".equalsIgnoreCase(type)) {
            return;
        }
        int limit = root.path("limit").asInt(20);
        int offset = root.path("offset").asInt(0);

        Map<String, Object> snapshot = staffCallQueryService.listForBooth(boothId, limit, offset);
        Map<String, Object> out = new HashMap<>();
        out.put("type", "LIST_RESULT");
        out.put("message", snapshot.get("message"));
        out.put("data", snapshot.get("data"));
        out.put("has_more", snapshot.get("has_more"));
        out.put("total", snapshot.get("total"));

        session.sendMessage(new TextMessage(objectMapper.writeValueAsString(out)));
    }

    public void broadcastSnapshot(Long boothId, Map<String, Object> snapshot) {
        Set<WebSocketSession> sessions = boothSessions.get(boothId);
        if (sessions == null || sessions.isEmpty()) {
            return;
        }
        try {
            Map<String, Object> out = new HashMap<>();
            out.put("type", "STAFF_CALL_SNAPSHOT");
            out.put("message", snapshot.get("message"));
            out.put("data", snapshot.get("data"));
            out.put("has_more", snapshot.get("has_more"));
            out.put("total", snapshot.get("total"));
            String json = objectMapper.writeValueAsString(out);
            TextMessage tm = new TextMessage(json);
            for (WebSocketSession s : sessions) {
                if (s.isOpen()) {
                    try {
                        s.sendMessage(tm);
                    } catch (IOException e) {
                        log.warn("[staffcall ws] 전송 실패 session={}", s.getId(), e);
                    }
                }
            }
        } catch (Exception e) {
            log.error("[staffcall ws] broadcast 실패", e);
        }
    }
}
