#!/bin/sh

# entrypoint.sh - Django 컨테이너 시작용 스크립트 입니더.
# 데이터베이스 연결이랑 migrate를 위해서 만든겁니다.
# DB/Redis 연결 대기는 docker-compose의 depends_on(service_healthy)이 보장합니다.
set -e

echo "=== Django 컨테이너 시작 ==="

# 로그 디렉토리 생성
mkdir -p /app/logs

# 데이터베이스 마이그레이션 실행
echo "데이터베이스 마이그레이션 실행 중..."
python manage.py migrate --noinput

# 정적 파일 수집
python manage.py collectstatic --noinput

echo "=== 초기화 완료 ==="

# Redis Listener 백그라운드 실행
echo "Redis Listener 시작 중 (백그라운드)..."
python manage.py listen_redis &

echo "Daphne 서버 시작 중..."

# 전달된 명령 실행 (CMD) ->  ["daphne", "-b", "0.0.0.0", "-p", "8000", "project.asgi:application"] 이 부분 말하는겨
exec "$@"
