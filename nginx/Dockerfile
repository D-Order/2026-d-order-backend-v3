# nginx 커스텀 이미지 - D-Order Backend v3
FROM nginx:alpine

# dev 또는 prod 설정 파일 선택 (기본값: dev)
ARG NGINX_ENV=dev

# 설정 파일을 템플릿으로 복사
COPY dev.conf /etc/nginx/nginx.conf.dev.template
COPY prod.conf /etc/nginx/nginx.conf.prod.template

# health check용 wget 설치
RUN apk add --no-cache wget

# 로그 디렉토리 권한 설정
RUN mkdir -p /var/log/nginx && \
    chown -R nginx:nginx /var/log/nginx

RUN mkdir -p /app/static && \
    chown -R nginx:nginx /app

# Let's Encrypt 디렉토리 생성
RUN mkdir -p /var/www/certbot

ENV NGINX_ENV=${NGINX_ENV}

EXPOSE 80 443

# 환경변수 치환 후 nginx 시작
CMD ["/bin/sh", "-c", "envsubst '${DOMAIN}' < /etc/nginx/nginx.conf.${NGINX_ENV}.template > /etc/nginx/nginx.conf && nginx -g 'daemon off;'"]
