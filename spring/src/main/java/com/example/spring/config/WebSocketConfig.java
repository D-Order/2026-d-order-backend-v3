package com.example.spring.config;

import com.example.spring.websocket.ServingWebSocketHandler;
import com.example.spring.websocket.CustomerStaffCallWebSocketHandler;
import com.example.spring.websocket.StaffCallWebSocketHandler;
import lombok.RequiredArgsConstructor;
import org.springframework.context.annotation.Configuration;
import org.springframework.web.socket.config.annotation.EnableWebSocket;
import org.springframework.web.socket.config.annotation.WebSocketConfigurer;
import org.springframework.web.socket.config.annotation.WebSocketHandlerRegistry;
import org.springframework.web.socket.server.support.HttpSessionHandshakeInterceptor;

@Configuration
@EnableWebSocket
@RequiredArgsConstructor
public class WebSocketConfig implements WebSocketConfigurer {

    private final ServingWebSocketHandler servingWebSocketHandler;
    private final StaffCallWebSocketHandler staffCallWebSocketHandler;
    private final CustomerStaffCallWebSocketHandler customerStaffCallWebSocketHandler;
    private final StaffCallHandshakeInterceptor staffCallHandshakeInterceptor;

    @Override
    public void registerWebSocketHandlers(WebSocketHandlerRegistry registry) {
        registry.addHandler(servingWebSocketHandler, "/ws/serving")
                .setAllowedOriginPatterns(
                        "http://localhost:5173",
                        "https://dev.dorder-api.shop",
                        "http://dev.dorder-api.shop",
                        "https://*.dorder-api.shop"
                )
                .addInterceptors(new HttpSessionHandshakeInterceptor());

        registry.addHandler(staffCallWebSocketHandler, "/ws/server/staffcall")
                .setAllowedOriginPatterns(
                        "http://localhost:5173",
                        "https://dev.dorder-api.shop",
                        "http://dev.dorder-api.shop",
                        "https://*.dorder-api.shop"
                )
                .addInterceptors(staffCallHandshakeInterceptor, new HttpSessionHandshakeInterceptor());

        registry.addHandler(customerStaffCallWebSocketHandler, "/ws/customer/staffcall")
                .setAllowedOriginPatterns(
                        "http://localhost:5173",
                        "https://dev.dorder-api.shop",
                        "http://dev.dorder-api.shop",
                        "https://*.dorder-api.shop"
                )
                .addInterceptors(new HttpSessionHandshakeInterceptor());
    }
}