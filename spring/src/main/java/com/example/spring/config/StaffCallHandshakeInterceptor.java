package com.example.spring.config;

import jakarta.servlet.http.Cookie;
import jakarta.servlet.http.HttpServletRequest;
import lombok.RequiredArgsConstructor;
import org.springframework.http.server.ServerHttpRequest;
import org.springframework.http.server.ServerHttpResponse;
import org.springframework.http.server.ServletServerHttpRequest;
import org.springframework.stereotype.Component;
import org.springframework.web.socket.WebSocketHandler;
import org.springframework.web.socket.server.HandshakeInterceptor;

import java.util.Map;

/**
 * 웹소켓 핸드셰이크 시 access_token 쿠키로 booth_id 및 session_id 확보
 */
@Component
@RequiredArgsConstructor
public class StaffCallHandshakeInterceptor implements HandshakeInterceptor {

    public static final String ATTR_BOOTH_ID = "boothId";
    public static final String ATTR_SESSION_ID = "sessionId";

    private final CookieUtil cookieUtil;
    private final JwtUtil jwtUtil;

    @Override
    public boolean beforeHandshake(ServerHttpRequest request, ServerHttpResponse response,
                                   WebSocketHandler wsHandler, Map<String, Object> attributes) {
        if (!(request instanceof ServletServerHttpRequest servletRequest)) {
            return false;
        }
        HttpServletRequest req = servletRequest.getServletRequest();
        Cookie[] cookies = req.getCookies();
        String token = cookieUtil.getAccessTokenFromCookies(cookies);
        if (token == null || !jwtUtil.validateToken(token)) {
            return false;
        }
        try {
            Long boothId = jwtUtil.getBoothIdFromToken(token);
            attributes.put(ATTR_BOOTH_ID, boothId);
            attributes.put(ATTR_SESSION_ID, jwtUtil.getSessionIdFromToken(token));
            return true;
        } catch (Exception e) {
            return false;
        }
    }

    @Override
    public void afterHandshake(ServerHttpRequest request, ServerHttpResponse response,
                               WebSocketHandler wsHandler, Exception exception) {
    }
}
