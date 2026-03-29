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

# Spring 유저 생성
psql -U postgres -d postgres <<-EOSQL
  CREATE USER $SPRING_USER WITH PASSWORD '$SPRING_DB_PASSWORD';
EOSQL

# 데이터베이스에 대한 권한 부여
psql -U postgres -d $DB_NAME <<-EOSQL
  GRANT CONNECT ON DATABASE $DB_NAME TO $SPRING_USER;
  GRANT USAGE ON SCHEMA public TO $SPRING_USER;
  ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO $SPRING_USER;
  ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT USAGE ON SEQUENCES TO $SPRING_USER;
EOSQL

# 기존 테이블에 대한 권한 부여 (이미 존재하는 테이블이 있는 경우)
psql -U postgres -d $DB_NAME <<-EOSQL
  GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO $SPRING_USER;
  GRANT USAGE ON ALL SEQUENCES IN SCHEMA public TO $SPRING_USER;
EOSQL

echo "Spring user '$SPRING_USER' created successfully~!~~!!~!~"
