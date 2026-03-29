from rest_framework import serializers
from booth.serializers import BoothSerializer

class UserBoothSignupSerializer(serializers.Serializer):
    """
    회원가입 요청 검증용 Serializer (검증만 담당, 생성 로직은 AuthService에 있음)
    """
    username = serializers.CharField(min_length=6, max_length=12)
    password = serializers.CharField(write_only=True, min_length=4, max_length=20)
    booth_data = BoothSerializer(write_only=True)

    # create() 메서드 없음 - 비즈니스 로직은 AuthService.signup_user()에서 처리


    