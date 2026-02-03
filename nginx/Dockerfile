# nginx 커스텀 이미지 - D-Order Backend v3 DEV
FROM nginx:alpine

# 설정 파일을 템플릿으로 복사
COPY dev.conf /etc/nginx/nginx.conf.template

# health check용 wget 설치
RUN apk add --no-cache wget

# 로그 디렉토리 권한 설정
RUN mkdir -p /var/log/nginx && \
    chown -R nginx:nginx /var/log/nginx

# 정적/미디어 파일 디렉토리 생성
RUN mkdir -p /app/static /app/media && \
    chown -R nginx:nginx /app

# Let's Encrypt 디렉토리 생성
RUN mkdir -p /var/www/certbot

EXPOSE 80 443

# 환경변수 치환 후 nginx 시작
CMD ["/bin/sh", "-c", "envsubst '${DOMAIN}' < /etc/nginx/nginx.conf.template > /etc/nginx/nginx.conf && nginx -g 'daemon off;'"]
