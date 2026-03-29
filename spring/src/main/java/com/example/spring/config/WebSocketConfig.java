package com.example.spring.config;

import com.example.spring.websocket.ServingWebSocketHandler;
import lombok.RequiredArgsConstructor;
import org.springframework.context.annotation.Configuration;
import org.springframework.web.socket.config.annotation.EnableWebSocket;
import org.springframework.web.socket.config.annotation.WebSocketConfigurer;
import org.springframework.web.socket.config.annotation.WebSocketHandlerRegistry;
import org.springframework.web.socket.server.support.HttpSessionHandshakeInterceptor; // 1. 임포트 추가

@Configuration
@EnableWebSocket
@RequiredArgsConstructor
public class WebSocketConfig implements WebSocketConfigurer {

    private final ServingWebSocketHandler servingWebSocketHandler;

    @Override
    public void registerWebSocketHandlers(WebSocketHandlerRegistry registry) {
        registry.addHandler(servingWebSocketHandler, "/ws/serving")
                // 2. 허용 도메인을 명확하게 지정 (패턴 사용)
                .setAllowedOriginPatterns(
                        "http://localhost:5173",
                        "https://dev.dorder-api.shop",
                        "http://dev.dorder-api.shop",
                        "https://*.dorder-api.shop" // 서브도메인 대비 안전장치
                )
                // 3. HTTP 세션 및 쿠키 정보를 웹소켓 핸드셰이크 시점에 유지해주는 인터셉터
                .addInterceptors(new HttpSessionHandshakeInterceptor());
    }
}