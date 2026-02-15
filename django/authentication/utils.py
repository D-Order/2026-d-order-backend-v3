"""
JWT 쿠키 유틸리티 함수
"""
from django.conf import settings


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

    # Access Token 쿠키 설정
    response.set_cookie(
        key=jwt_settings.get('AUTH_COOKIE'),
        value=access_token,
        max_age=int(jwt_settings.get('ACCESS_TOKEN_LIFETIME').total_seconds()),
        httponly=jwt_settings.get('AUTH_COOKIE_HTTP_ONLY'),
        samesite=jwt_settings.get('AUTH_COOKIE_SAMESITE'),
        secure=jwt_settings.get('AUTH_COOKIE_SECURE'),
    )

    # Refresh Token 쿠키 설정
    response.set_cookie(
        key=jwt_settings.get('AUTH_COOKIE_REFRESH'),
        value=refresh_token,
        max_age=int(jwt_settings.get('REFRESH_TOKEN_LIFETIME').total_seconds()),
        httponly=jwt_settings.get('AUTH_COOKIE_HTTP_ONLY'),
        samesite=jwt_settings.get('AUTH_COOKIE_SAMESITE'),
        secure=jwt_settings.get('AUTH_COOKIE_SECURE'),
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

    response.delete_cookie(jwt_settings.get('AUTH_COOKIE'))
    response.delete_cookie(jwt_settings.get('AUTH_COOKIE_REFRESH'))

    return response
