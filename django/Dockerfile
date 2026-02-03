FROM python:3.12-alpine

# 작업 디렉토리 설정
# 요건 docker 내부 경로
WORKDIR /app

# 시스템 패키지 설치
RUN apk add --no-cache \
    gcc \
    musl-dev \
    postgresql-dev \
    postgresql-client \
    python3-dev \
    libffi-dev \
    openssl-dev \
    redis \
    curl \
    icu-data-full

# 컨테이너 내부 사용자 권한을 위한 사용자 및 그룹 생성
# docker는 기본적으로 root 권한으로 실행 일반 유저를 만들어서 권한 낮추기
RUN addgroup -g 1000 appuser && \
    adduser -D -u 1000 -G appuser appuser


COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 프로젝트 코드 복사
COPY . .

# entrypoint.sh 실행 권한 부여
RUN chmod +x entrypoint.sh

# 소유권 변경
RUN chown -R appuser:appuser /app

# 일반 사용자로 전환
USER appuser

# 헬스체크 추가
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Entrypoint 설정
ENTRYPOINT ["/app/entrypoint.sh"]

# Daphne 서버 실행
CMD ["daphne", "-b", "0.0.0.0", "-p", "8000", "project.asgi:application"]
