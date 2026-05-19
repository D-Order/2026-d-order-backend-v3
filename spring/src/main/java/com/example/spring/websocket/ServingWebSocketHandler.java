package com.example.spring.websocket;

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

@Slf4j
@Component
@RequiredArgsConstructor
public class ServingWebSocketHandler extends TextWebSocketHandler {

    private final Map<Long, Set<WebSocketSession>> boothSessions = new ConcurrentHashMap<>();
    private final ObjectMapper objectMapper;

    @Override
    public void afterConnectionEstablished(WebSocketSession session) {
        Object boothAttr = session.getAttributes().get(ATTR_BOOTH_ID);
        if (!(boothAttr instanceof Long boothId)) {
            log.warn("[serving ws] boothId 속성이 없어 연결 종료 session={}", session.getId());
            try {
                session.close(CloseStatus.NOT_ACCEPTABLE);
            } catch (IOException e) {
                log.warn("[serving ws] 연결 종료 실패 session={}", session.getId(), e);
            }
            return;
        }

        boothSessions.computeIfAbsent(boothId, key -> ConcurrentHashMap.newKeySet()).add(session);
        log.info("[serving ws] 연결 boothId={}, session={}", boothId, session.getId());
    }

    @Override
    public void afterConnectionClosed(WebSocketSession session, CloseStatus status) {
        Object boothAttr = session.getAttributes().get(ATTR_BOOTH_ID);
        if (boothAttr instanceof Long boothId) {
            Set<WebSocketSession> sessions = boothSessions.get(boothId);
            if (sessions != null) {
                sessions.remove(session);
                if (sessions.isEmpty()) {
                    boothSessions.remove(boothId);
                }
            }
            log.info("[serving ws] 연결 해제 boothId={}, session={}, status={}", boothId, session.getId(), status);
        } else {
            log.info("[serving ws] 연결 해제(boothId 없음) session={}, status={}", session.getId(), status);
        }
    }

    public void broadcastEvent(Long boothId, String eventType, Object data) {
        if (boothId == null) {
            log.warn("[serving ws] boothId null로 이벤트 전송 스킵 eventType={}", eventType);
            return;
        }

        Set<WebSocketSession> sessions = boothSessions.get(boothId);
        int targetCount = sessions == null ? 0 : sessions.size();
        log.info("[serving ws] 이벤트 브로드캐스트 boothId={}, eventType={}, targets={}", boothId, eventType, targetCount);

        if (sessions == null || sessions.isEmpty()) {
            return;
        }

        try {
            Map<String, Object> payload = new HashMap<>();
            payload.put("type", eventType);
            payload.put("data", data);

            TextMessage textMessage = new TextMessage(objectMapper.writeValueAsString(payload));

            for (WebSocketSession session : sessions) {
                if (!session.isOpen()) {
                    sessions.remove(session);
                    continue;
                }
                try {
                    session.sendMessage(textMessage);
                } catch (IOException e) {
                    sessions.remove(session);
                    log.warn("[serving ws] 전송 실패 boothId={}, session={}", boothId, session.getId(), e);
                }
            }

            if (sessions.isEmpty()) {
                boothSessions.remove(boothId);
            }
        } catch (Exception e) {
            log.error("[serving ws] 이벤트 직렬화 실패 boothId={}, eventType={}", boothId, eventType, e);
        }
    }
}