#!/bin/bash
# PostgreSQL 초기화 스크립트
# Spring용 추가 유저 생성

set -e

# 환경변수 사용 (docker-compose에서 전달)
SPRING_USER=${SPRING_DB_USER}
SPRING_DB_PASSWORD=${SPRING_DB_PASSWORD}
DB_NAME=${POSTGRES_DB}

# PostgreSQL이 준비될 때까지 대기
until pg_isready -U postgres; do
  echo "Waiting for PostgreSQL..."
  sleep 1
done

# Spring 유저 생성 (재실행해도 안전하도록 존재 여부 확인)
USER_EXISTS=$(psql -U postgres -tAc "SELECT 1 FROM pg_roles WHERE rolname='$SPRING_USER'")
if [ "$USER_EXISTS" = "1" ]; then
  psql -U postgres -d postgres <<-EOSQL
    ALTER USER $SPRING_USER WITH PASSWORD '$SPRING_DB_PASSWORD';
EOSQL
else
  psql -U postgres -d postgres <<-EOSQL
    CREATE USER $SPRING_USER WITH PASSWORD '$SPRING_DB_PASSWORD';
EOSQL
fi

# 데이터베이스에 대한 권한 부여
# CREATE 권한은 Spring 전용 테이블(staff_call, serving_task 등) 생성에 필요.
# Django 테이블은 owner=postgres라 Spring이 ALTER/DROP 할 수 없어 권한 격리는 유지됨.
psql -U postgres -d $DB_NAME <<-EOSQL
  GRANT CONNECT ON DATABASE $DB_NAME TO $SPRING_USER;
  GRANT USAGE, CREATE ON SCHEMA public TO $SPRING_USER;
  ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO $SPRING_USER;
  ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT USAGE ON SEQUENCES TO $SPRING_USER;
EOSQL

# 기존 테이블에 대한 권한 부여 (이미 존재하는 테이블이 있는 경우)
psql -U postgres -d $DB_NAME <<-EOSQL
  GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO $SPRING_USER;
  GRANT USAGE ON ALL SEQUENCES IN SCHEMA public TO $SPRING_USER;
EOSQL

echo "Spring user '$SPRING_USER' created successfully~!~~!!~!~"
