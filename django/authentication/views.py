from django.conf import settings
from django.shortcuts import get_object_or_404
import jwt
from rest_framework.views import APIView
from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer, TokenRefreshSerializer
from django.contrib.auth import authenticate
from django.contrib.auth.models import User

from authentication.serializers import UserBoothSignupSerializer
from booth.serializers import BoothSerializer
from rest_framework.response import Response



class SignupView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = UserBoothSignupSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            user = serializer.instance

            res = Response({
                "message": "회원가입이 완료되었습니다.",
                "data": {
                    "username": user.username,
                    "booth_id" : user.id,
                },
            }, status=status.HTTP_201_CREATED)



            token = TokenObtainPairSerializer.get_token(user)
            refresh_token = str(token)
            access_token = str(token.access_token)

            jwt_settings = settings.SIMPLE_JWT
            # access token
            res.set_cookie(
                jwt_settings.get('AUTH_COOKIE'),
                access_token,
                httponly=jwt_settings.get('AUTH_COOKIE_HTTP_ONLY'),
                samesite=jwt_settings.get('AUTH_COOKIE_SAMESITE'),
                secure=jwt_settings.get('AUTH_COOKIE_SECURE'),
            )

            # refresh token
            res.set_cookie(
                jwt_settings.get('AUTH_COOKIE_REFRESH'),
                refresh_token,
                httponly=jwt_settings.get('AUTH_COOKIE_HTTP_ONLY'),
                samesite=jwt_settings.get('AUTH_COOKIE_SAMESITE'),
                secure=jwt_settings.get('AUTH_COOKIE_SECURE'),
            )

            return res
        return Response({
            "message": "회원가입에 실패했습니다.",
            "data": serializer.errors,
        }, status=status.HTTP_400_BAD_REQUEST)
    
class CheckUsernameView(APIView):
    def get(self, request):
        username = request.query_params.get("username")

        if not username:
            return Response({
                "message": "username 파라미터가 필요합니다.",
                "data": None
            }, status=status.HTTP_400_BAD_REQUEST)

        is_available = not User.objects.filter(username=username).exists()

        return Response({
            "message": "아이디 중복체크에 성공했습니다.",
            "data": {
                "is_available": is_available
            }
        }, status=status.HTTP_200_OK)

class AuthApiView(APIView):
    permission_classes = [AllowAny]

    #  로그인 
    def post(self, request):
        username = request.data.get("username")
        password = request.data.get("password")

        # 1. 아이디 확인
        try:
            user = User.objects.get(username=username)
        except User.DoesNotExist:
            return Response({
                "message": "일치하지 않는 아이디에요",
                "data": None
            }, status=status.HTTP_401_UNAUTHORIZED)

        # 2. 비밀번호 확인
        user = authenticate(username=username, password=password)
        if not user:
            return Response({
                "message": "일치하지 않는 비밀번호에요.",
                "data": None
            }, status=status.HTTP_401_UNAUTHORIZED)


        # 3. 응답
        res = Response({
            "message": "로그인 성공",
            "data": {
                "username": user.username,
                "booth_id": user.id
            }
        }, status=status.HTTP_200_OK)
            
        # 4. 토큰 발급
        token = TokenObtainPairSerializer.get_token(user)
        refresh_token = str(token)
        access_token = str(token.access_token)
        
        jwt_settings = settings.SIMPLE_JWT

        # access token
        res.set_cookie(
            jwt_settings.get('AUTH_COOKIE'),
            access_token,
            httponly=jwt_settings.get('AUTH_COOKIE_HTTP_ONLY'),
            samesite=jwt_settings.get('AUTH_COOKIE_SAMESITE'),
            secure=jwt_settings.get('AUTH_COOKIE_SECURE'),
        )

        # refresh token
        res.set_cookie(
            jwt_settings.get('AUTH_COOKIE_REFRESH'),
            refresh_token,
            httponly=jwt_settings.get('AUTH_COOKIE_HTTP_ONLY'),
            samesite=jwt_settings.get('AUTH_COOKIE_SAMESITE'),
            secure=jwt_settings.get('AUTH_COOKIE_SECURE'),
        )

        return res

    # 로그아웃
    def delete(self, request):
        jwt_settings = settings.SIMPLE_JWT
        res = Response({
            "message": "로그아웃 성공",
            "data": None
        }, status=200)

        # access token 삭제
        res.delete_cookie(jwt_settings.get('AUTH_COOKIE'))

        # refresh token 삭제
        res.delete_cookie(jwt_settings.get('AUTH_COOKIE_REFRESH'))

        return res
    
    # 토큰 재발급
    def get(self, request):
        jwt_settings = settings.SIMPLE_JWT
        try:
            access_token = request.COOKIES.get(jwt_settings.get('AUTH_COOKIE'))
            if not access_token:
                raise jwt.InvalidTokenError

            payload = jwt.decode(access_token, settings.SECRET_KEY, algorithms=["HS256"])
            user_id = payload.get("user_id")
            user = get_object_or_404(User, pk=user_id)

            return Response({
                "message": "Access 토큰 유효",
                "data": {
                    "username" : user.username, 
                    "booth_id": user.pk,
                }
            }, status=status.HTTP_200_OK)

        except jwt.ExpiredSignatureError:
            # access token 만료 시 refresh token 으로 재발급
            refresh_token = request.COOKIES.get(jwt_settings.get('AUTH_COOKIE_REFRESH'))
            if not refresh_token:
                return Response({
                    "message": "Refresh 토큰 없음",
                    "data": None
                }, status=status.HTTP_401_UNAUTHORIZED)
            serializer = TokenRefreshSerializer(data={"refresh": refresh_token})
            if serializer.is_valid(raise_exception=True):
                new_access = serializer.data["access"]
                payload = jwt.decode(new_access, settings.SECRET_KEY, algorithms=["HS256"])
                user_id = payload.get("user_id")
                user = get_object_or_404(User, pk=user_id)


                res = Response({
                    "message": "access 토큰 재발급 완료",
                    "data": {
                        "username": user.username,
                        "booth_id": user.pk,
                    }
                }, status=status.HTTP_200_OK)

                res.set_cookie(
                    jwt_settings.get('AUTH_COOKIE'),
                    new_access,
                    httponly=jwt_settings.get('AUTH_COOKIE_HTTP_ONLY'),
                    samesite=jwt_settings.get('AUTH_COOKIE_SAMESITE'),
                    secure=jwt_settings.get('AUTH_COOKIE_SECURE'),
                )
                return res

        except jwt.InvalidTokenError:
            return Response({
                "message": "Refresh 토큰이 유효하지 않음",
                "data": None
            }, status=status.HTTP_401_UNAUTHORIZED)


    


