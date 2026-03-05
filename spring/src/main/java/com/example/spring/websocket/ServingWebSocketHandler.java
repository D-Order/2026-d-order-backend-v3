package com.example.spring.websocket;

import lombok.extern.slf4j.Slf4j;
import org.springframework.stereotype.Component;
import org.springframework.web.socket.CloseStatus;
import org.springframework.web.socket.TextMessage;
import org.springframework.web.socket.WebSocketSession;
import org.springframework.web.socket.handler.TextWebSocketHandler;

import java.io.IOException;
import java.util.Set;
import java.util.concurrent.ConcurrentHashMap;

@Slf4j
@Component
public class ServingWebSocketHandler extends TextWebSocketHandler {

    // 현재 접속 중인 태블릿(프론트엔드)들의 목록을 기억하는 수첩입니다.
    private final Set<WebSocketSession> sessions = ConcurrentHashMap.newKeySet();

    // 프론트엔드가 처음 접속했을 때
    @Override
    public void afterConnectionEstablished(WebSocketSession session) {
        sessions.add(session);
        log.info("[웹소켓 접속] 새 태블릿 연결됨: {}", session.getId());
    }

    // 프론트엔드가 접속을 끊었을 때 (창 닫기 등)
    @Override
    public void afterConnectionClosed(WebSocketSession session, CloseStatus status) {
        sessions.remove(session);
        log.info("[웹소켓 해제] 태블릿 연결 끊김: {}", session.getId());
    }

    // [핵심 기능] 사내 방송(새로운 서빙 대기)이 들리면, 접속 중인 모두에게 데이터를 쏴줍니다!
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
}