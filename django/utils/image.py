import io
import uuid
from datetime import datetime
from PIL import Image, UnidentifiedImageError
from django.core.files.uploadedfile import InMemoryUploadedFile
from rest_framework import serializers
from rest_framework.exceptions import APIException


# 이미지 설정
MAX_IMAGE_SIZE_MB = 5  # 업로드 최대 용량 (MB)
MAX_IMAGE_SIZE_BYTES = MAX_IMAGE_SIZE_MB * 1024 * 1024
COMPRESS_QUALITY = 85  # 압축 품질 (1-100)
MAX_DIMENSION = 1920  # 최대 가로/세로 크기
ALLOWED_IMAGE_FORMATS = ['JPEG', 'JPG', 'PNG', 'GIF', 'WEBP']
ALLOWED_EXTENSIONS = ['jpg', 'jpeg', 'png', 'gif', 'webp']


# 커스텀 예외 클래스
class FileTooLargeException(APIException):
    """413 이미지 용량 초과"""
    status_code = 413
    default_detail = '이미지 파일 용량이 너무 큽니다.'
    default_code = 'FILE_TOO_LARGE'


class UnsupportedImageFormatException(APIException):
    """415 지원하지 않는 이미지 형식"""
    status_code = 415
    default_detail = '지원하지 않는 파일 형식입니다.'
    default_code = 'UNSUPPORTED_IMAGE_FORMAT'


# ==========================================
# 이미지 파일명 및 경로 생성 함수
# ==========================================

def generate_menu_image_path(instance, filename):
    """
    메뉴 이미지 파일 경로 생성
    경로: booth_{booth_id}/menu_images/menu_{uuid}.jpg
    
    Example: booth_1/menu_images/menu_550e8400-e29b-41d4-a716-446655440000.jpg
    """
    try:
        booth_id = instance.booth_id or instance.booth.pk
    except (AttributeError, ValueError, TypeError):
        booth_id = "unknown"
    
    unique_filename = f"menu_{uuid.uuid4()}.jpg"
    return f"booth_{booth_id}/menu_images/{unique_filename}"


def generate_setmenu_image_path(instance, filename):
    """
    세트메뉴 이미지 파일 경로 생성
    경로: booth_{booth_id}/setmenu_images/setmenu_{uuid}.jpg
    
    Example: booth_1/setmenu_images/setmenu_550e8400-e29b-41d4-a716-446655440000.jpg
    """
    try:
        booth_id = instance.booth_id or instance.booth.pk
    except (AttributeError, ValueError, TypeError):
        booth_id = "unknown"
    
    unique_filename = f"setmenu_{uuid.uuid4()}.jpg"
    return f"booth_{booth_id}/setmenu_images/{unique_filename}"


def validate_image_size(image):
    """이미지 용량 검증 (5MB 제한)"""
    if image and image.size > MAX_IMAGE_SIZE_BYTES:
        raise FileTooLargeException(
            detail=f'이미지 파일 용량이 너무 큽니다. (최대 {MAX_IMAGE_SIZE_MB}MB)',
        )
    return image


def validate_image_format(image):
    """이미지 형식 검증 (jpg, png 등)"""
    if not image:
        return image
    
    # 확장자 검사
    ext = image.name.rsplit('.', 1)[-1].lower() if '.' in image.name else ''
    if ext not in ALLOWED_EXTENSIONS:
        raise UnsupportedImageFormatException(
            detail=f'지원하지 않는 파일 형식입니다. {", ".join(ALLOWED_EXTENSIONS)} 파일만 업로드 가능합니다.',
        )
    
    # 실제 이미지 형식 검사
    try:
        img = Image.open(image)
        if img.format and img.format.upper() not in ALLOWED_IMAGE_FORMATS:
            raise UnsupportedImageFormatException(
                detail=f'지원하지 않는 파일 형식입니다. {", ".join(ALLOWED_EXTENSIONS)} 파일만 업로드 가능합니다.',
            )
        image.seek(0)  # 파일 포인터 리셋
    except UnidentifiedImageError:
        raise UnsupportedImageFormatException(
            detail='유효한 이미지 파일이 아닙니다.',
        )
    
    return image


def compress_image(image):
    """
    이미지 압축 및 리사이즈
    - 최대 1920px로 리사이즈
    - JPEG로 변환하여 압축
    """
    if not image:
        return None
    
    # 이미지 열기
    img = Image.open(image)
    
    # RGBA면 RGB로 변환 (JPEG는 알파채널 미지원)
    if img.mode in ('RGBA', 'P'):
        img = img.convert('RGB')
    
    # 리사이즈 (비율 유지)
    if img.width > MAX_DIMENSION or img.height > MAX_DIMENSION:
        img.thumbnail((MAX_DIMENSION, MAX_DIMENSION), Image.Resampling.LANCZOS)
    
    # 압축하여 저장
    output = io.BytesIO()
    img.save(output, format='JPEG', quality=COMPRESS_QUALITY, optimize=True)
    output.seek(0)
    
    # 파일명은 단순하게: upload_to 함수에서 최종 경로를 생성함
    # compress_image에서는 확장자만 .jpg로 정규화
    simple_name = "image.jpg"
    
    # InMemoryUploadedFile로 반환
    return InMemoryUploadedFile(
        file=output,
        field_name='image',
        name=simple_name,
        content_type='image/jpeg',
        size=output.getbuffer().nbytes,
        charset=None
    )


class CompressedImageField(serializers.ImageField):
    """압축 + 용량/형식 검증이 포함된 이미지 필드"""
    
    def to_internal_value(self, data):
        # 기본 검증
        file = super().to_internal_value(data)
        
        # 용량 검증 (413)
        validate_image_size(file)
        
        # 형식 검증 (415)
        validate_image_format(file)
        
        # 압축
        compressed = compress_image(file)
        
        return compressed if compressed else file
