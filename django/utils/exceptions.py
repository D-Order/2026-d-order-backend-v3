import logging
from rest_framework.views import exception_handler
from rest_framework.response import Response
from utils.image import FileTooLargeException, UnsupportedImageFormatException

logger = logging.getLogger(__name__)


def custom_exception_handler(exc, context):
    """
    커스텀 예외 핸들러
    - 413, 415 에러 형식 맞춤
    """
    # 기본 DRF 예외 처리
    response = exception_handler(exc, context)
    
    # 413 이미지 용량 초과
    if isinstance(exc, FileTooLargeException):
        return Response({
            "message": str(exc.detail),
            "code": exc.default_code
        }, status=413)
    
    # 415 지원하지 않는 이미지 형식
    if isinstance(exc, UnsupportedImageFormatException):
        return Response({
            "message": str(exc.detail),
            "code": exc.default_code
        }, status=415)
    
    # 401 인증 실패
    if response is not None and response.status_code == 401:
        return Response({
            "message": "로그인이 필요합니다.",
            "code": "AUTHENTICATION_FAILED"
        }, status=401)
    
    # 500 서버 오류 (response가 None이면 처리되지 않은 예외)
    if response is None:
        # 실제 에러 로깅
        logger.exception(f"Unhandled exception: {exc}")
        print(f"[ERROR] Unhandled exception: {exc}")  # 콘솔 출력
        import traceback
        traceback.print_exc()
        
        return Response({
            "message": "서버 내부 오류가 발생했습니다. 잠시 후 다시 시도해주세요.",
            "code": "INTERNAL_SERVER_ERROR"
        }, status=500)
    
    # detail → message 키 변환
    if response is not None and 'detail' in response.data:
        response.data['message'] = response.data.pop('detail')

    return response
