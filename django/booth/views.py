from django.shortcuts import render

from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.views import APIView

# Create your views here.
class BoothMyPageAPI(APIView):
    """부스 마이페이지 열람 / 정보 수정 API"""
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        """마이페이지 열람"""
        pass

    def patch(self, request):
        """마이페이지 정보 수정"""
        pass

class BoothMyPageQRcodeAPI(APIView):
    """부스 QR 다운로드"""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        """QR 다운로드"""
        pass

class BoothAPI(APIView):
    """부스 이름 조회용"""
    permission_classes = [AllowAny]

    def get(self,request):
        """부스 이름 조회용

        Args:
            request (_type_): _description_
        """
        pass
