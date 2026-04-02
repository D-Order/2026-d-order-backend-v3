package com.example.spring.config;

import lombok.Getter;
import lombok.Setter;
import org.springframework.boot.context.properties.ConfigurationProperties;
import org.springframework.stereotype.Component;

/**
 * JWT 관련 설정을 application.yml에서 바인딩
 */
@Component
@ConfigurationProperties(prefix = "jwt")
@Getter
@Setter
public class JwtProperties {

    private String secretKey;
    private long accessTokenExpiration;
    private long refreshTokenExpiration;
    private Cookie cookie = new Cookie();

    @Getter
    @Setter
    public static class Cookie {
        private String accessTokenName = "access_token";
        private String refreshTokenName = "refresh_token";
        private boolean httpOnly = true;
        private String sameSite = "Lax";
        private boolean secure = false;
        private String domain = ""; // 로컬: 빈 문자열 = Domain 속성 생략, prod: .dorder-api.shop
    }
}
