from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework.parsers import MultiPartParser, FormParser, JSONParser
from rest_framework import status
from rest_framework.exceptions import ValidationError

from .models import Menu, SetMenu
from .serializers import MenuSerializer, MenuUpdateSerializer, SetMenuSerializer
from .services import MenuService, SetMenuService


class MenuAPIView(APIView):
    """
    메뉴 등록 API
    POST /api/v3/menus/
    """
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser, JSONParser]
    
    def post(self, request):
        """메뉴 등록"""
        booth = request.user.booth
        
        serializer = MenuSerializer(data=request.data)
        
        if not serializer.is_valid():
            return Response({
                "message": "입력값 유효성 검사 실패",
                "errors": serializer.errors
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # 메뉴 생성
        menu = MenuService.create_menu(booth, serializer.validated_data)
        
        # 응답 직렬화
        response_serializer = MenuSerializer(menu)
        
        return Response({
            "message": "메뉴 등록 성공",
            "data": response_serializer.data
        }, status=status.HTTP_201_CREATED)


class MenuDetailAPIView(APIView):
    """
    메뉴 수정/삭제 API
    PATCH /api/v3/menus/<menu_id>/
    DELETE /api/v3/menus/<menu_id>/
    """
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser, JSONParser]
    
    def get_menu(self, menu_id, booth, action='modify'):
        """
        메뉴 조회 + 권한 검증
        action: 'modify' (수정) 또는 'delete' (삭제)
        """
        try:
            menu = Menu.objects.get(id=menu_id)
        except Menu.DoesNotExist:
            if action == 'delete':
                message = "이미 삭제되었거나 존재하지 않는 메뉴입니다."
            else:
                message = "수정하려는 메뉴 정보를 찾을 수 없습니다."
            return None, Response({
                "message": message,
                "code": "MENU_NOT_FOUND"
            }, status=status.HTTP_404_NOT_FOUND)
        
        # 권한 검증: 해당 부스의 메뉴인지 확인
        if menu.booth.pk != booth.pk:
            if action == 'delete':
                message = "해당 메뉴를 삭제할 수 있는 권한이 없습니다."
            else:
                message = "해당 메뉴를 수정할 권한이 없습니다."
            return None, Response({
                "message": message,
                "code": "PERMISSION_DENIED"
            }, status=status.HTTP_403_FORBIDDEN)
        
        return menu, None
    
    def patch(self, request, menu_id):
        """메뉴 수정"""
        booth = request.user.booth
        
        menu, error_response = self.get_menu(menu_id, booth)
        if error_response:
            return error_response
        
        serializer = MenuUpdateSerializer(menu, data=request.data, partial=True, context={'request': request})
        
        if not serializer.is_valid():
            return Response({
                "message": "데이터 수정 형식이 올바르지 않습니다.",
                "errors": serializer.errors
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # 메뉴 수정
        menu = MenuService.update_menu(menu, serializer.validated_data)
        
        # 응답 직렬화
        response_serializer = MenuSerializer(menu)
        
        return Response({
            "message": "메뉴 수정 성공",
            "data": response_serializer.data
        }, status=status.HTTP_200_OK)
    
    def delete(self, request, menu_id):
        """메뉴 삭제"""
        booth = request.user.booth
        
        menu, error_response = self.get_menu(menu_id, booth, action='delete')
        if error_response:
            return error_response
        
        # 삭제 전 menu_id 저장
        deleted_menu_id = menu.id
        
        # 메뉴 삭제 (이미지 파일 포함)
        MenuService.delete_menu(menu)
        
        return Response({
            "message": "메뉴 삭제 성공",
            "data": {
                "menu_id": deleted_menu_id
            }
        }, status=status.HTTP_200_OK)

