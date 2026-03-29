from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework.parsers import MultiPartParser, FormParser, JSONParser
from rest_framework import status
from rest_framework.exceptions import ValidationError
from booth.models import Booth
from .models import Menu, SetMenu, SetMenuItem
from .serializers import MenuSerializer, MenuUpdateSerializer, SetMenuSerializer, SetMenuUpdateSerializer
from .services import MenuService, SetMenuService
import json
from django.db.models import Min
from django.shortcuts import get_object_or_404
from table.models import Table

class MenuAPIView(APIView):
    """
    메뉴 등록 API
    POST /api/v3/django/booth/menus/
    """
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser, JSONParser]
    def post(self, request):
        booth = request.user.booth
        serializer = MenuSerializer(data=request.data)
        if not serializer.is_valid():
            return Response({
                "message": "입력값 유효성 검사 실패",
                "errors": serializer.errors
            }, status=status.HTTP_400_BAD_REQUEST)
        menu = MenuService.create_menu(booth, serializer.validated_data)
        response_serializer = MenuSerializer(menu)
        return Response({
            "message": "메뉴 등록 성공",
            "data": response_serializer.data
        }, status=status.HTTP_201_CREATED)

class MenuDetailAPIView(APIView):
    """
    메뉴 수정/삭제 API
    PATCH /api/v3/django/booth/menus/<menu_id>/
    DELETE /api/v3/django/booth/menus/<menu_id>/
    """
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser, JSONParser]
    def get_menu(self, menu_id, booth, action='modify'):
        try:
            menu = Menu.objects.get(id=menu_id)
        except Menu.DoesNotExist:
            message = "수정하려는 메뉴 정보를 찾을 수 없습니다." if action == 'modify' else "이미 삭제되었거나 존재하지 않는 메뉴입니다."
            return None, Response({
                "message": message,
                "code": "MENU_NOT_FOUND"
            }, status=status.HTTP_404_NOT_FOUND)
        if menu.booth.pk != booth.pk:
            message = "해당 메뉴를 수정할 권한이 없습니다." if action == 'modify' else "해당 메뉴를 삭제할 권한이 없습니다."
            return None, Response({
                "message": message,
                "code": "PERMISSION_DENIED"
            }, status=status.HTTP_403_FORBIDDEN)
        return menu, None
    def patch(self, request, menu_id):
        booth = request.user.booth
        menu, error_response = self.get_menu(menu_id, booth)
        if error_response:
            return error_response
        serializer = MenuUpdateSerializer(menu, data=request.data, partial=True, context={'request': request})
        if not serializer.is_valid():
            return Response({
                "message": "입력값 유효성 검사 실패",
                "errors": serializer.errors
            }, status=status.HTTP_400_BAD_REQUEST)
        menu = MenuService.update_menu(menu, serializer.validated_data)
        response_serializer = MenuSerializer(menu)
        return Response({
            "message": "메뉴 수정 성공",
            "data": response_serializer.data
        }, status=status.HTTP_200_OK)
    def delete(self, request, menu_id):
        booth = request.user.booth
        menu, error_response = self.get_menu(menu_id, booth, action='delete')
        if error_response:
            return error_response
        deleted_menu_id = menu.id
        MenuService.delete_menu(menu)
        return Response({
            "message": "메뉴 삭제 성공",
            "data": {"menu_id": deleted_menu_id}
        }, status=status.HTTP_200_OK)

class SetMenuAPIView(APIView):
    """
    세트메뉴 등록 API
    POST /api/v3/django/booth/sets/
    """
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser, JSONParser]
    def post(self, request):
        booth = request.user.booth
        if hasattr(request.data, 'dict'):
            data = {}
            for key in request.data:
                if key == 'set_items':
                    try:
                        data['set_items'] = json.loads(request.data.get('set_items'))
                    except json.JSONDecodeError:
                        return Response({
                            "message": "입력값 유효성 검사 실패",
                            "errors": {"set_items": "유효하지 않은 JSON 형식입니다."}
                        }, status=status.HTTP_400_BAD_REQUEST)
                elif key == 'image':
                    data['image'] = request.data.get('image')
                else:
                    data[key] = request.data.get(key)
        else:
            data = request.data
        serializer = SetMenuSerializer(data=data)
        if not serializer.is_valid():
            return Response({
                "message": "입력값 유효성 검사 실패",
                "errors": serializer.errors
            }, status=status.HTTP_400_BAD_REQUEST)
        set_menu = SetMenuService.create_set_menu(booth, serializer.validated_data)
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
        try:
            set_menu = SetMenu.objects.get(id=set_id)
        except SetMenu.DoesNotExist:
            message = "수정하려는 세트메뉴 정보를 찾을 수 없습니다." if action == 'modify' else "이미 삭제되었거나 존재하지 않는 세트메뉴입니다."
            return None, Response({
                "message": message,
                "code": "MENU_NOT_FOUND"
            }, status=status.HTTP_404_NOT_FOUND)
        if set_menu.booth.pk != booth.pk:
            message = "해당 세트메뉴를 수정할 권한이 없습니다." if action == 'modify' else "해당 세트메뉴를 삭제할 권한이 없습니다."
            return None, Response({
                "message": message,
                "code": "PERMISSION_DENIED"
            }, status=status.HTTP_403_FORBIDDEN)
        return set_menu, None
    def patch(self, request, set_id):
        booth = request.user.booth
        set_menu, error_response = self.get_set_menu(set_id, booth)
        if error_response:
            return error_response
        if hasattr(request.data, 'dict'):
            data = {}
            for key in request.data:
                if key == 'set_items':
                    try:
                        data['set_items'] = json.loads(request.data.get('set_items'))
                    except json.JSONDecodeError:
                        return Response({
                            "message": "데이터 수정 형식이 올바르지 않습니다.",
                            "errors": {"set_items": "유효하지 않은 JSON 형식입니다."}
                        }, status=status.HTTP_400_BAD_REQUEST)
                elif key == 'image':
                    data['image'] = request.data.get('image')
                else:
                    data[key] = request.data.get(key)
        else:
            data = request.data
        serializer = SetMenuUpdateSerializer(set_menu, data=data, partial=True, context={'request': request})
        if not serializer.is_valid():
            return Response({
                "message": "데이터 수정 형식이 올바르지 않습니다.",
                "errors": serializer.errors
            }, status=status.HTTP_400_BAD_REQUEST)
        set_menu = SetMenuService.update_set_menu(set_menu, serializer.validated_data)
        response_serializer = SetMenuSerializer(set_menu)
        return Response({
            "message": "세트메뉴 수정 성공",
            "data": response_serializer.data
        }, status=status.HTTP_200_OK)
    def delete(self, request, set_id):
        booth = request.user.booth
        set_menu, error_response = self.get_set_menu(set_id, booth, action='delete')
        if error_response:
            return error_response
        deleted_set_id = set_menu.id
        SetMenuService.delete_set_menu(set_menu)
        return Response({
            "message": "메뉴 삭제 성공",
            "data": {"set_id": deleted_set_id}
        }, status=status.HTTP_200_OK)

class BoothMenuListAPIView(APIView):
    """
    운영자 부스 전체 메뉴판 조회 API
    GET /api/v3/django/booth/menus/
    """
    permission_classes = [IsAuthenticated]
    def get(self, request):
        user = request.user
        booth = getattr(user, 'booth', None)
        if not booth:
            return Response({
                "message": "부스 정보를 찾을 수 없습니다.",
                "code": "MENU_NOT_FOUND"
            }, status=status.HTTP_404_NOT_FOUND)
        data = []
        
        # FEE 메뉴 조회 및 추가
        fee_menu = Menu.objects.filter(booth=booth, category='FEE').first()
        if fee_menu:
            fee_item = {
                "id": fee_menu.pk,
                "name": fee_menu.name,
                "price": int(fee_menu.price),
                "category": fee_menu.category,
                "description": fee_menu.description or "",
                "image": fee_menu.image.url if fee_menu.image else None,
                "stock": fee_menu.stock,
                "is_soldout": fee_menu.stock == 0,
                "is_fixed": True,
                "created_at": fee_menu.created_at.isoformat() if hasattr(fee_menu, 'created_at') else None
            }
            data.append(fee_item)
        
        menus = Menu.objects.filter(booth=booth).exclude(category="FEE").order_by("id")
        for menu in menus:
            data.append({
                "id": menu.pk,
                "name": menu.name,
                "price": int(menu.price),
                "category": menu.category,
                "description": menu.description or "",
                "image": menu.image.url if menu.image else None,
                "stock": menu.stock,
                "is_soldout": menu.stock == 0,
                "is_fixed": False,
                "created_at": menu.created_at.isoformat() if hasattr(menu, 'created_at') else None
            })
        set_menus = SetMenu.objects.filter(booth=booth).order_by("id")
        for setmenu in set_menus:
            # 각 구성품별 (menu.stock // quantity) 계산
            item_stocks = [item.menu.stock // item.quantity for item in setmenu.items.all() if item.menu.stock is not None and item.quantity > 0]
            min_stock = min(item_stocks) if item_stocks else 0
            is_soldout = any(item.menu.stock == 0 for item in setmenu.items.all())
            data.append({
                "id": setmenu.pk,
                "name": setmenu.name,
                "price": setmenu.price,
                "category": "SET",
                "description": setmenu.description or "",
                "image": setmenu.image.url if setmenu.image else None,
                "stock": min_stock,
                "is_soldout": is_soldout,
                "is_fixed": False,
                "created_at": setmenu.created_at.isoformat() if hasattr(setmenu, 'created_at') else None
            })
        return Response({
            "message": "운영자 메뉴 목록 조회 완료",
            "booth_id": booth.pk,
            "data": data
        }, status=status.HTTP_200_OK)

class UserMenuListAPIView(APIView):
    """
    사용자 메뉴판 조회 API
    GET /api/v3/django/booth/<int:booth_id>/menu-list/?table_number=xxx
    """
    permission_classes = []  # 로그인 없이 접근 가능
    def get(self, request, booth_id):
        table_num = request.GET.get('table_num')
        booth = get_object_or_404(Booth, pk=booth_id)
        table_info = None
        if table_num is not None:
            try:
                table_num_int = int(table_num)
            except (ValueError, TypeError):
                return Response({
                    "message": "유효하지 않은 테이블 번호입니다.",
                    "code": "TABLE_NUMBER_INVALID"
                }, status=status.HTTP_400_BAD_REQUEST)
            table_obj = Table.objects.filter(booth=booth, table_num=table_num_int).first()
            if not table_obj:
                return Response({
                    "message": "존재하지 않는 테이블 번호입니다.",
                    "code": "TABLE_NOT_FOUND"
                }, status=status.HTTP_404_NOT_FOUND)
            usage = table_obj.usages.order_by('-started_at').first()
            table_info = {
                "table_number": table_num_int,
                "table_usage_id": usage.id if usage else None
            }
        # FEE 메뉴 조회 및 추가
        fee_data = []
        fee_menu = Menu.objects.filter(booth=booth, category='FEE').first()
        if fee_menu:
            fee_data = [{
                "id": fee_menu.pk,
                "name": fee_menu.name,
                "price": int(fee_menu.price),
                "description": fee_menu.description or "",
                "image": fee_menu.image.url if fee_menu.image else None,
                "is_soldout": fee_menu.stock == 0
            }]
        # SET
        set_menus = SetMenu.objects.filter(booth=booth).order_by('-price')
        set_data = []
        for setmenu in set_menus:
            origin_price = sum([item.menu.price * item.quantity for item in setmenu.items.all()])
            discount_rate = round((origin_price - setmenu.price) / origin_price * 100, 1) if origin_price > 0 else 0.0
            is_soldout = any(item.menu.stock == 0 for item in setmenu.items.all())
            set_data.append({
                "id": setmenu.pk,
                "name": setmenu.name,
                "origin_price": int(origin_price),
                "price": setmenu.price,
                "discount_rate": discount_rate,
                "description": setmenu.description or "",
                "image": setmenu.image.url if setmenu.image else None,
                "is_soldout": is_soldout
            })
        set_data.sort(key=lambda x: x['price'], reverse=True)
        # MENU
        menu_data = []
        menus = Menu.objects.filter(booth=booth, category="MENU").order_by('-price')
        for menu in menus:
            menu_data.append({
                "id": menu.pk,
                "name": menu.name,
                "price": int(menu.price),
                "description": menu.description or "",
                "image": menu.image.url if menu.image else None,
                "is_soldout": menu.stock == 0
            })
        # DRINK
        drink_data = []
        drinks = Menu.objects.filter(booth=booth, category="DRINK").order_by('-price')
        for drink in drinks:
            drink_data.append({
                "id": drink.pk,
                "name": drink.name,
                "price": int(drink.price),
                "description": drink.description or "",
                "image": drink.image.url if drink.image else None,
                "is_soldout": drink.stock == 0
            })
        resp = {
            "message": "메뉴판 조회 완료",
            "booth_id": booth.pk,
            "booth_name": booth.name,
            "seat_type": booth.seat_type,
            "data": {
                "FEE": fee_data,
                "SET": set_data,
                "MENU": menu_data,
                "DRINK": drink_data
            }
        }
        if table_info:
            resp["table_info"] = table_info
        return Response(resp, status=status.HTTP_200_OK)

