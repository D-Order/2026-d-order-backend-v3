# ============================================================
# Spring Boot Dockerfile - Multi-stage Build
# ============================================================
# 멀티스테이지 빌드를 사용하는 이유:
# 1. 빌드 도구(Gradle, JDK full)는 최종 이미지에 포함 안됨 → 이미지 크기 감소
# 2. 빌드 캐시 활용으로 재빌드 시간 단축
# 3. 보안: 빌드 시점 파일들이 런타임에 노출되지 않음
# ============================================================

# ========================
# Stage 1: Build Stage
# ========================
FROM gradle:8.14-jdk17 AS builder

WORKDIR /app

# Gradle 캐시를 위해 의존성 파일만 먼저 복사
# 의존성이 변경되지 않으면 이 레이어는 캐시됨 → 빌드 속도 향상
COPY build.gradle settings.gradle ./
COPY gradle ./gradle

# 의존성 다운로드 (캐시 레이어)
RUN gradle dependencies --no-daemon || true

# 소스 코드 복사 및 빌드
COPY src ./src
RUN gradle bootJar --no-daemon -x test

# ========================
# Stage 2: Runtime Stage
# ========================
# alpine 대신 일반 이미지 사용 (Apple Silicon M1/M2/M3 ARM 호환)
FROM eclipse-temurin:17-jre

WORKDIR /app

# 보안: 비-root 사용자 생성
# UID/GID 1000은 이미 존재할 수 있으므로 1001 사용 우분투가 1000으로 미리만들어서 쓰고있음
# eclipse-temurin:17-jre 이미지는 Ubuntu 기반, 그리고 Ubuntu 이미지들은 제작될 때부터 ubuntu라는 사용자를 UID 1000으로 만들어 놓는다고함.
RUN groupadd -g 1001 appgroup && \
    useradd -u 1001 -g appgroup -m appuser

# 빌드된 JAR 파일만 복사 (나머지는 버림)
COPY --from=builder /app/build/libs/*.jar app.jar

# 권한 설정
RUN chown appuser:appgroup app.jar && \
    mkdir -p /app/logs && \
    chown appuser:appgroup /app/logs

# 비-root 사용자로 전환
USER appuser

# 헬스체크 설정
# /health 엔드포인트로 서비스 상태 확인
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD curl -f http://localhost:8080/health || exit 1

# 컨테이너 포트 노출 (문서화 목적)
EXPOSE 8080

# JVM 옵션 설명:
# -XX:+UseContainerSupport: 컨테이너 리소스 제한 인식
# -XX:MaxRAMPercentage=75.0: 컨테이너 메모리의 75%까지 사용
# -Djava.security.egd: 빠른 랜덤 생성 (컨테이너에서 엔트로피 부족 해결)
ENTRYPOINT ["java", \
    "-XX:+UseContainerSupport", \
    "-XX:MaxRAMPercentage=75.0", \
    "-Djava.security.egd=file:/dev/./urandom", \
    "-jar", "app.jar"]

# 기본 프로필은 docker-compose에서 환경변수로 오버라이드
CMD ["--spring.profiles.active=dev"]
