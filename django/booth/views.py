from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.views import APIView
from rest_framework import status
from rest_framework.response import Response
from booth.services import BoothService
from booth.models import Booth
from booth.serializers import BoothSerializer, BoothUpdateSerializer

# Create your views here.
class BoothMyPageAPIView(APIView):
    """부스 마이페이지 열람 / 정보 수정 API"""
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        """마이페이지 열람"""
        user = request.user
        booth = user.booth

        serializer = BoothSerializer(booth)

        return Response({
            "message": "부스 데이터를 불러왔습니다.",
            "data" : serializer.data
        }, status=status.HTTP_200_OK)

    def patch(self, request):
        """마이페이지 정보 수정"""
        user = request.user
        booth = user.booth

        serializer = BoothUpdateSerializer(booth, data=request.data, partial = True)
        
        # 유효성 검증
        serializer.is_valid(raise_exception=True)

        BoothService.update_booth(booth, serializer.validated_data)

        return Response({
            "message": "업데이트가 완료되었습니다.",
            "data" : serializer.data
        }, status=status.HTTP_200_OK)

class BoothMyPageQRcodeAPIView(APIView):
    """부스 QR URL"""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        """QR URL 반환"""
        booth = request.user.booth

        return Response({
            "message": "QR URL을 조회하였습니다.",
            "data" : {
                "qr_image_url" : booth.qr_image.url,
            }
        }, status=status.HTTP_200_OK)

class BoothNameAPIView(APIView):
    """부스 이름 조회용"""
    permission_classes = [AllowAny]

    def get(self,request, booth_id):

        # 못찾을때
        try:
            booth = Booth.objects.get(pk = booth_id)
        except Booth.DoesNotExist:
            return Response({
                "message" : "해당 부스를 찾을 수 없습니다."
            }, status=status.HTTP_404_NOT_FOUND)
    

        return Response({
            "message": "부스 이름을 조회하였습니다.",
            "data" : {
                "booth_name" : booth.name,
            }
        }, status=status.HTTP_200_OK)
