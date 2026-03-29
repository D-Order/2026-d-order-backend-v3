import logging
from contextlib import contextmanager


# 디스크에 저장하지 않고 메모리에 저장하는 설정입니다.
# @override_settings 데코레이터와 함께 사용하여 테스트 중에 파일 저장 동작을 수정할 수 있어요.
IN_MEMORY_STORAGES = {
    "default": {
        "BACKEND": "django.core.files.storage.InMemoryStorage",
    },
    "staticfiles": {
        "BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage",
    },
}


@contextmanager
def suppress_request_warnings():
    """의도적인 Bad Request 테스트 시 로그 억제"""
    logger = logging.getLogger('django.request')
    previous_level = logger.level
    logger.setLevel(logging.ERROR)
    try:
        yield
    finally:
        logger.setLevel(previous_level)

