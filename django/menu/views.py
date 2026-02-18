from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework.parsers import MultiPartParser, FormParser, JSONParser
from rest_framework import status
from rest_framework.exceptions import ValidationError

from .models import Menu, SetMenu
from .serializers import MenuSerializer, MenuUpdateSerializer, SetMenuSerializer, SetMenuUpdateSerializer
from .services import MenuService, SetMenuService
import json


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


class SetMenuAPIView(APIView):
    """
    세트메뉴 등록 API
    POST /api/v3/django/booth/sets/
    """
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser, JSONParser]
    
    def post(self, request):
        """세트메뉴 등록"""
        booth = request.user.booth
        
        # request.data 처리 (QueryDict → dict 변환 및 set_items JSON 파싱)
        if hasattr(request.data, 'dict'):
            # MultiPartParser/FormParser인 경우 (QueryDict)
            data = {}
            for key in request.data:
                if key == 'set_items':
                    # set_items는 JSON 문자열로 들어옴
                    try:
                        data['set_items'] = json.loads(request.data.get('set_items'))
                    except json.JSONDecodeError:
                        return Response({
                            "message": "입력값 유효성 검사 실패",
                            "errors": {
                                "set_items": "유효하지 않은 JSON 형식입니다."
                            }
                        }, status=status.HTTP_400_BAD_REQUEST)
                elif key == 'image':
                    # 파일은 그대로
                    data['image'] = request.data.get('image')
                else:
                    # 일반 필드
                    data[key] = request.data.get(key)
        else:
            # JSONParser인 경우 (이미 dict)
            data = request.data
        
        serializer = SetMenuSerializer(data=data)
        
        if not serializer.is_valid():
            return Response({
                "message": "입력값 유효성 검사 실패",
                "errors": serializer.errors
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # 세트메뉴 생성
        set_menu = SetMenuService.create_set_menu(booth, serializer.validated_data)
        
        # 응답 직렬화
        response_serializer = SetMenuSerializer(set_menu)
        
        return Response({
            "message": "세트메뉴 등록 성공",
            "data": response_serializer.data
        }, status=status.HTTP_201_CREATED)


class SetMenuDetailAPIView(APIView):
    """
    세트메뉴 수정/삭제 API
    PATCH /api/v3/django/booth/sets/<set_id>/
    DELETE /api/v3/django/booth/sets/<set_id>/
    """
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser, JSONParser]
    
    def get_set_menu(self, set_id, booth, action='modify'):
        """
        세트메뉴 조회 + 권한 검증
        action: 'modify' (수정) 또는 'delete' (삭제)
        """
        try:
            set_menu = SetMenu.objects.get(id=set_id)
        except SetMenu.DoesNotExist:
            if action == 'delete':
                message = "이미 삭제되었거나 존재하지 않는 세트메뉴입니다."
            else:
                message = "수정하려는 세트메뉴 정보를 찾을 수 없습니다."
            return None, Response({
                "message": message,
                "code": "MENU_NOT_FOUND"
            }, status=status.HTTP_404_NOT_FOUND)
        
        # 권한 검증: 해당 부스의 세트메뉴인지 확인
        if set_menu.booth.pk != booth.pk:
            if action == 'delete':
                message = "해당 세트메뉴를 삭제할 권한이 없습니다."
            else:
                message = "해당 세트메뉴를 수정할 권한이 없습니다."
            return None, Response({
                "message": message,
                "code": "PERMISSION_DENIED"
            }, status=status.HTTP_403_FORBIDDEN)
        
        return set_menu, None
    
    def patch(self, request, set_id):
        """세트메뉴 수정"""
        booth = request.user.booth
        
        set_menu, error_response = self.get_set_menu(set_id, booth)
        if error_response:
            return error_response
        
        # request.data 처리 (QueryDict → dict 변환 및 set_items JSON 파싱)
        if hasattr(request.data, 'dict'):
            # MultiPartParser/FormParser인 경우 (QueryDict)
            data = {}
            for key in request.data:
                if key == 'set_items':
                    try:
                        data['set_items'] = json.loads(request.data.get('set_items'))
                    except json.JSONDecodeError:
                        return Response({
                            "message": "데이터 수정 형식이 올바르지 않습니다.",
                            "errors": {
                                "set_items": "유효하지 않은 JSON 형식입니다."
                            }
                        }, status=status.HTTP_400_BAD_REQUEST)
                elif key == 'image':
                    data['image'] = request.data.get('image')
                else:
                    data[key] = request.data.get(key)
        else:
            data = request.data
        
        serializer = SetMenuUpdateSerializer(
            set_menu, 
            data=data, 
            partial=True, 
            context={'request': request}
        )
        
        if not serializer.is_valid():
            return Response({
                "message": "데이터 수정 형식이 올바르지 않습니다.",
                "errors": serializer.errors
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # 세트메뉴 수정
        set_menu = SetMenuService.update_set_menu(set_menu, serializer.validated_data)
        
        # 응답 직렬화
        response_serializer = SetMenuSerializer(set_menu)
        
        return Response({
            "message": "세트메뉴 수정 성공",
            "data": response_serializer.data
        }, status=status.HTTP_200_OK)
    
    def delete(self, request, set_id):
        """세트메뉴 삭제"""
        booth = request.user.booth
        
        set_menu, error_response = self.get_set_menu(set_id, booth, action='delete')
        if error_response:
            return error_response
        
        # 삭제 전 set_id 저장
        deleted_set_id = set_menu.id
        
        # 세트메뉴 삭제 (이미지 파일 + SetMenuItem CASCADE 삭제)
        SetMenuService.delete_set_menu(set_menu)
        
        return Response({
            "message": "메뉴 삭제 성공",
            "data": {
                "set_id": deleted_set_id
            }
        }, status=status.HTTP_200_OK)

