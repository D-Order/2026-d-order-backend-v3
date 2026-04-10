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

@Slf4j
@Component
@RequiredArgsConstructor
public class ServingWebSocketHandler extends TextWebSocketHandler {

    private final Set<WebSocketSession> sessions = ConcurrentHashMap.newKeySet();
    private final ObjectMapper objectMapper;

    @Override
    public void afterConnectionEstablished(WebSocketSession session) {
        sessions.add(session);
        log.info("[웹소켓 접속] 새 태블릿 연결됨: {}", session.getId());
    }

    @Override
    public void afterConnectionClosed(WebSocketSession session, CloseStatus status) {
        sessions.remove(session);
        log.info("[웹소켓 해제] 태블릿 연결 끊김: {}", session.getId());
    }

    public void broadcastMessage(String message) {
        TextMessage textMessage = new TextMessage(message);
        for (WebSocketSession session : sessions) {
            try {
                if (session.isOpen()) {
                    session.sendMessage(textMessage);
                }
            } catch (IOException e) {
                log.error("[웹소켓 전송 실패] session: {}", session.getId(), e);
            }
        }
    }

    public void broadcastEvent(String eventType, Object data) {
        try {
            Map<String, Object> payload = new HashMap<>();
            payload.put("type", eventType);
            payload.put("data", data);

            String jsonMessage = objectMapper.writeValueAsString(payload);
            broadcastMessage(jsonMessage);
        } catch (Exception e) {
            log.error("[웹소켓 이벤트 직렬화 실패]", e);
        }
    }
}