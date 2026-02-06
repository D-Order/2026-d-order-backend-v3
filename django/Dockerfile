# syntax=docker/dockerfile:1
FROM python:3.12-slim

WORKDIR /app

# 런타임 필수 패키지만 설치 (빌드 도구 불필요)
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 \
    curl \
    && rm -rf /var/lib/apt/lists/*

# 일반 사용자 생성 (보안)
RUN groupadd -g 1000 appuser && \
    useradd -u 1000 -g appuser -m appuser

# pip 캐시 마운트로 재빌드 시 빠름
COPY requirements.txt .
RUN --mount=type=cache,target=/root/.cache/pip \
    pip install -r requirements.txt

# 프로젝트 코드 복사 및 권한 설정
COPY --chown=appuser:appuser . .
RUN chmod +x entrypoint.sh

USER appuser

# 헬스체크 추가
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Entrypoint 설정
ENTRYPOINT ["/app/entrypoint.sh"]

# Daphne 서버 실행
CMD ["daphne", "-b", "0.0.0.0", "-p", "8000", "project.asgi:application"]