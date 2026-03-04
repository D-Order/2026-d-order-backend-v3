package com.example.spring.config;

import com.example.spring.websocket.ServingWebSocketHandler;
import lombok.RequiredArgsConstructor;
import org.springframework.context.annotation.Configuration;
import org.springframework.web.socket.config.annotation.EnableWebSocket;
import org.springframework.web.socket.config.annotation.WebSocketConfigurer;
import org.springframework.web.socket.config.annotation.WebSocketHandlerRegistry;

@Configuration
@EnableWebSocket // 웹소켓 기능 켜기
@RequiredArgsConstructor
public class WebSocketConfig implements WebSocketConfigurer {

    private final ServingWebSocketHandler servingWebSocketHandler;

    @Override
    public void registerWebSocketHandlers(WebSocketHandlerRegistry registry) {
        // 프론트엔드가 접속할 주소를 열어줍니다: ws://localhost:8080/ws/serving
        registry.addHandler(servingWebSocketHandler, "/ws/serving")
                .setAllowedOrigins("*"); // 지금은 테스트를 위해 모두 허용 (실전엔 프론트 도메인만)
    }
}