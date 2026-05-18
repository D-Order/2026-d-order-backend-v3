"""
JWT 쿠키 유틸리티 함수
"""
from django.conf import settings


# 과거 도메인 설정(`.dorder-api.shop`, `dev.dorder-api.shop` 등) 시기에
# 사용자 브라우저에 박힌 잔재 쿠키를 자동 정리하기 위한 도메인/이름 변형 목록.
# delete_cookie는 Set-Cookie의 Domain attr이 정확히 일치해야 브라우저가 지우므로
# 알려진 모든 변형을 시도해야 한다.
_STALE_COOKIE_DOMAINS = (
    '.dorder-api.shop',
    'dorder-api.shop',
    'dev.dorder-api.shop',
    '.dev.dorder-api.shop',
    'prod.dorder-api.shop',
    '.prod.dorder-api.shop',
)
_STALE_COOKIE_NAMES = ('csrftoken', 'sessionid', 'access_token', 'refresh_token')


def clear_stale_domain_cookies(response):
    """옛 도메인 쿠키(부모도메인/서브도메인 변형)를 모두 expire 처리한다."""
    for domain in _STALE_COOKIE_DOMAINS:
        for name in _STALE_COOKIE_NAMES:
            response.delete_cookie(name, domain=domain, path='/')
    return response


def set_jwt_cookies(response, access_token, refresh_token):
    """
    Response 객체에 JWT 쿠키를 설정합니다.

    Args:
        response: Django Response 객체
        access_token: JWT access token 문자열
        refresh_token: JWT refresh token 문자열

    Returns:
        response: 쿠키가 설정된 Response 객체
    """
    jwt_settings = settings.SIMPLE_JWT
    domain = jwt_settings.get('AUTH_COOKIE_DOMAIN')

    # Access Token 쿠키 설정
    response.set_cookie(
        key=jwt_settings.get('AUTH_COOKIE'),
        value=access_token,
        max_age=int(jwt_settings.get('ACCESS_TOKEN_LIFETIME').total_seconds()),
        httponly=jwt_settings.get('AUTH_COOKIE_HTTP_ONLY'),
        samesite=jwt_settings.get('AUTH_COOKIE_SAMESITE'),
        secure=jwt_settings.get('AUTH_COOKIE_SECURE'),
        domain=domain,
    )

    # Refresh Token 쿠키 설정
    response.set_cookie(
        key=jwt_settings.get('AUTH_COOKIE_REFRESH'),
        value=refresh_token,
        max_age=int(jwt_settings.get('REFRESH_TOKEN_LIFETIME').total_seconds()),
        httponly=jwt_settings.get('AUTH_COOKIE_HTTP_ONLY'),
        samesite=jwt_settings.get('AUTH_COOKIE_SAMESITE'),
        secure=jwt_settings.get('AUTH_COOKIE_SECURE'),
        domain=domain,
    )

    return response


def delete_jwt_cookies(response):
    """
    Response 객체에서 JWT 쿠키를 삭제합니다.

    Args:
        response: Django Response 객체

    Returns:
        response: 쿠키가 삭제된 Response 객체
    """
    jwt_settings = settings.SIMPLE_JWT

    samesite = jwt_settings.get('AUTH_COOKIE_SAMESITE')
    domain = jwt_settings.get('AUTH_COOKIE_DOMAIN')

    response.delete_cookie(jwt_settings.get('AUTH_COOKIE'), samesite=samesite, domain=domain)
    response.delete_cookie(jwt_settings.get('AUTH_COOKIE_REFRESH'), samesite=samesite, domain=domain)

    return response
