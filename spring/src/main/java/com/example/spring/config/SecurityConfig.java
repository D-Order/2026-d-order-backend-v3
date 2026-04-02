package com.example.spring.config;

import com.example.spring.security.ServerApiJwtFilter;
import lombok.RequiredArgsConstructor;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.security.config.annotation.web.builders.HttpSecurity;
import org.springframework.security.config.annotation.web.configuration.EnableWebSecurity;
import org.springframework.security.config.annotation.web.configurers.AbstractHttpConfigurer;
import org.springframework.security.config.http.SessionCreationPolicy;
import org.springframework.security.web.SecurityFilterChain;
import org.springframework.security.web.authentication.UsernamePasswordAuthenticationFilter;
import org.springframework.web.cors.CorsConfiguration;
import org.springframework.web.cors.CorsConfigurationSource;
import org.springframework.web.cors.UrlBasedCorsConfigurationSource;

import java.util.Arrays;
import java.util.List;

/**
 * Spring Security 설정
 * - 세션 비활성화 (JWT 쿠키 인증 사용)
 * - CSRF 비활성화 (쿠키 기반 JWT 사용)
 * - CORS 설정
 */
@Configuration
@EnableWebSecurity
@RequiredArgsConstructor
public class SecurityConfig {

    private final ServerApiJwtFilter serverApiJwtFilter;

    /**
     * Spring Security 필터 체인 설정
     */
    @Bean
    public SecurityFilterChain filterChain(HttpSecurity http) throws Exception {
        http
                .addFilterBefore(serverApiJwtFilter, UsernamePasswordAuthenticationFilter.class)
                // CSRF 비활성화 (JWT 쿠키 사용)
                .csrf(AbstractHttpConfigurer::disable)

                // CORS 설정
                .cors(cors -> cors.configurationSource(corsConfigurationSource()))

                // 세션 비활성화 (Stateless)
                .sessionManagement(session ->
                        session.sessionCreationPolicy(SessionCreationPolicy.STATELESS)
                )

                // URL 접근 권한 설정
                .authorizeHttpRequests(auth -> auth
                        // 인증 API는 모두 허용
                        .requestMatchers("/api/v3/spring/auth/**").permitAll()
                        // 헬스체크 허용
                        .requestMatchers("/health").permitAll()
                        // 테스트 API 허용
                        .requestMatchers("/ws/**", "/ws/serving/**").permitAll()
                        // 🌟 웹소켓 경로 추가 및 서빙 API 완전 개방 (테스트용)
                        .requestMatchers("/api/v3/spring/test/**").permitAll()
                        // 그 외 모든 요청 허용 (필요시 인증 필요로 변경)
                        .anyRequest().permitAll()
                )

                // 기본 폼 로그인 비활성화
                .formLogin(AbstractHttpConfigurer::disable)

                // HTTP Basic 인증 비활성화
                .httpBasic(AbstractHttpConfigurer::disable);

        return http.build();
    }

    /**
     * CORS 설정
     * Django와 동일한 설정
     */
    @Bean
    public CorsConfigurationSource corsConfigurationSource() {
        CorsConfiguration configuration = new CorsConfiguration();

        // 허용할 Origin (로컬 개발 환경)
        configuration.setAllowedOrigins(Arrays.asList(
                "http://localhost:3000",
                "http://localhost:5173",
                "https://localhost:5173",
                "http://localhost:5174",
                "https://localhost:5174",
                "http://127.0.0.1:3000",
                "http://127.0.0.1:5173",
                "https://127.0.0.1:5173",
                "http://127.0.0.1:5174",
                "https://127.0.0.1:5174",
                "https://dev.dorder-api.shop",
                "http://dev.dorder-api.shop",
                "https://admin.dorder-api.shop",
                "https://customer.dorder-api.shop",
                "https://server.dorder-api.shop"
        ));

        // 허용할 HTTP 메서드
        configuration.setAllowedMethods(Arrays.asList(
                "GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"
        ));

        // 허용할 헤더
        configuration.setAllowedHeaders(List.of("*"));

        // 쿠키 포함 허용
        configuration.setAllowCredentials(true);

        // 노출할 헤더 (에러 응답에도 노출)
        configuration.setExposedHeaders(Arrays.asList(
                "Set-Cookie", "Authorization"
        ));

        UrlBasedCorsConfigurationSource source = new UrlBasedCorsConfigurationSource();
        source.registerCorsConfiguration("/**", configuration);

        return source;
    }
}
