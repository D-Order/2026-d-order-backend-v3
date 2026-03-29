package com.example.spring.security;

import com.example.spring.config.CookieUtil;
import com.example.spring.config.JwtUtil;
import jakarta.servlet.FilterChain;
import jakarta.servlet.ServletException;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpServletResponse;
import lombok.RequiredArgsConstructor;
import org.springframework.http.MediaType;
import org.springframework.stereotype.Component;
import org.springframework.web.filter.OncePerRequestFilter;

import java.io.IOException;
import java.nio.charset.StandardCharsets;

/**
 * {@code /server/**} 서버(직원) API — access_token 쿠키 필수
 */
@Component
@RequiredArgsConstructor
public class ServerApiJwtFilter extends OncePerRequestFilter {

    public static final String ATTR_BOOTH_ID = "BOOTH_ID";

    private final CookieUtil cookieUtil;
    private final JwtUtil jwtUtil;

    @Override
    protected void doFilterInternal(HttpServletRequest request, HttpServletResponse response, FilterChain filterChain)
            throws ServletException, IOException {
        String path = request.getRequestURI();
        if (!path.startsWith("/server/")) {
            filterChain.doFilter(request, response);
            return;
        }
        if ("OPTIONS".equalsIgnoreCase(request.getMethod())) {
            filterChain.doFilter(request, response);
            return;
        }

        String token = cookieUtil.getAccessTokenFromCookies(request.getCookies());
        if (token == null || !jwtUtil.validateToken(token)) {
            response.setStatus(HttpServletResponse.SC_UNAUTHORIZED);
            response.setContentType(MediaType.APPLICATION_JSON_VALUE);
            response.setCharacterEncoding(StandardCharsets.UTF_8.name());
            response.getWriter().write("{\"message\":\"인증이 필요합니다.\"}");
            return;
        }
        try {
            Long boothId = jwtUtil.getBoothIdFromToken(token);
            request.setAttribute(ATTR_BOOTH_ID, boothId);
            request.setAttribute("ACCESS_TOKEN", token);
        } catch (Exception e) {
            response.setStatus(HttpServletResponse.SC_UNAUTHORIZED);
            response.setContentType(MediaType.APPLICATION_JSON_VALUE);
            response.setCharacterEncoding(StandardCharsets.UTF_8.name());
            response.getWriter().write("{\"message\":\"유효하지 않은 토큰입니다.\"}");
            return;
        }
        filterChain.doFilter(request, response);
    }
}
