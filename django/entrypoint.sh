#!/bin/sh

# entrypoint.sh - Django 컨테이너 시작용 스크립트 입니더.
# 데이터베이스 연결이랑 migrate를 위해서 만든겁니다.
set -e

echo "=== Django 컨테이너 시작 ==="

# PostgreSQL 연결 확인
echo "PostgreSQL 연결 대기 중..."
until PGPASSWORD=$DB_PASSWORD psql -h "$DB_HOST" -U "$DB_USER" -d "$DB_NAME" -c '\q' 2>/dev/null; do
  echo "PostgreSQL이 아직 준비되지 않았습니다 - 대기 중..."
  sleep 2
done

echo "PostgreSQL 연결"

# Redis 연결 확인
echo "Redis 연결 확인 중..."
if [ -n "$REDIS_PASSWORD" ]; then
  # Redis 비밀번호가 설정된 경우
  until redis-cli -h "$REDIS_HOST" -p "$REDIS_PORT" -a "$REDIS_PASSWORD" ping 2>/dev/null | grep -q PONG; do
    echo "Redis가 아직 준비되지 않았습니다 - 대기 중..."
    sleep 2
  done
else
  # Redis 비밀번호가 없는 경우
  until redis-cli -h "$REDIS_HOST" -p "$REDIS_PORT" ping 2>/dev/null | grep -q PONG; do
    echo "redis 비밀번호가 설정되지 않았습니다 - 무한대기중"
    sleep 2
  done
fi

echo "Redis 연결 성공!"

chown -R $(whoami):$(whoami) /app/static /app/media

# 데이터베이스 마이그레이션 실행
echo "데이터베이스 마이그레이션 실행 중..."
python manage.py migrate --noinput

# 정적 파일 수집
python manage.py collectstatic --noinput

echo "=== 초기화 완료 ==="
echo "Daphne 서버 시작 중..."

# 전달된 명령 실행 (CMD) ->  ["daphne", "-b", "0.0.0.0", "-p", "8000", "project.asgi:application"] 이 부분 말하는겨
exec "$@"
