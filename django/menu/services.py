from django.db import transaction
from rest_framework.exceptions import ValidationError
from .models import Menu, SetMenu, SetMenuItem
from order.models import OrderItem


class MenuService:
    """Menu 비즈니스 로직"""
    
    @staticmethod
    @transaction.atomic
    def create_menu(booth, validated_data):
        """
        메뉴 생성
        - 트랜잭션으로 DB 저장과 이미지 업로드 관리
        """
        menu = Menu.objects.create(booth=booth, **validated_data)
        return menu
    
    @staticmethod
    @transaction.atomic
    def update_menu(menu, validated_data):
        """메뉴 수정 (이미지 삭제 포함)"""
        # 이미지 삭제 처리
        image_delete = validated_data.pop('image_delete', False)
        if image_delete and menu.image:
            menu.image.delete(save=False)
            menu.image = None
        
        # 나머지 필드 업데이트
        for attr, value in validated_data.items():
            setattr(menu, attr, value)
        menu.save()
        return menu
    
    @staticmethod
    @transaction.atomic
    def delete_menu(menu):
        """
        메뉴 삭제
        - 해당 메뉴가 활성 주문에 있으면 삭제 불가능
        - 해당 메뉴를 포함하는 세트메뉴도 함께 삭제
        - 이미지 파일도 함께 삭제
        """
        # 1. 활성 주문(COOKING, COOKED, SERVING) 확인
        active_order_item = OrderItem.objects.filter(
            menu=menu,
            status__in=['COOKING', 'COOKED', 'SERVING']
        ).first()
        
        if active_order_item:
            raise ValidationError(
                f"현재 활성 주문(주문 ID: {active_order_item.order_id})에 포함된 메뉴입니다. 삭제할 수 없습니다."
            )
        
        # 2. 해당 메뉴를 포함하는 세트메뉴 찾기
        set_menus_to_delete = SetMenu.objects.filter(
            items__menu=menu
        ).distinct()
        
        # 각 세트메뉴 삭제 전 활성 주문 확인
        for set_menu in set_menus_to_delete:
            set_menu_active_order = OrderItem.objects.filter(
                setmenu=set_menu,
                status__in=['COOKING', 'COOKED', 'SERVING']
            ).first()
            
            if set_menu_active_order:
                raise ValidationError(
                    f"해당 메뉴를 포함하는 세트메뉴('{set_menu.name}')가 "
                    f"활성 주문(주문 ID: {set_menu_active_order.order_id})에 있습니다. "
                    f"삭제할 수 없습니다."
                )
        
        # 3. 이미지 파일 및 세트메뉴 삭제
        if menu.image:
            try:
                menu.image.delete(save=False)
            except Exception:
                pass  # 이미지 삭제 실패는 무시
        
        # 세트메뉴 이미지도 삭제
        for set_menu in set_menus_to_delete:
            if set_menu.image:
                try:
                    set_menu.image.delete(save=False)
                except Exception:
                    pass
            set_menu.delete()
        
        # 4. DB 레코드 삭제
        menu.delete()


class SetMenuService:
    """SetMenu 비즈니스 로직"""
    
    @staticmethod
    @transaction.atomic
    def create_set_menu(booth, validated_data):
        """
        세트메뉴 생성
        - SetMenu + SetMenuItem 함께 생성
        """
        set_items_data = validated_data.pop('set_items')
        
        # SetMenu 생성
        set_menu = SetMenu.objects.create(booth=booth, **validated_data)
        
        # SetMenuItem 생성
        for item_data in set_items_data:
            SetMenuItem.objects.create(
                set_menu=set_menu,
                menu_id=item_data['menu_id'],
                quantity=item_data.get('quantity', 1)
            )
        
        return set_menu
    
    @staticmethod
    @transaction.atomic
    def update_set_menu(set_menu, validated_data):
        """세트메뉴 수정 (이미지 삭제 포함)"""
        set_items_data = validated_data.pop('set_items', None)
        
        # 이미지 삭제 처리
        image_delete = validated_data.pop('image_delete', False)
        if image_delete and set_menu.image:
            set_menu.image.delete(save=False)
            set_menu.image = None
        
        # SetMenu 필드 업데이트
        for attr, value in validated_data.items():
            setattr(set_menu, attr, value)
        set_menu.save()
        
        # SetMenuItem 갱신 (기존 삭제 후 새로 생성)
        if set_items_data is not None:
            set_menu.items.all().delete()
            for item_data in set_items_data:
                SetMenuItem.objects.create(
                    set_menu=set_menu,
                    menu_id=item_data['menu_id'],
                    quantity=item_data.get('quantity', 1)
                )
        
        return set_menu
    
    @staticmethod
    @transaction.atomic
    def delete_set_menu(set_menu):
        """
        세트메뉴 삭제
        - 활성 주문에 포함되면 삭제 불가능
        - 이미지 파일도 함께 삭제
        - SetMenuItem은 CASCADE로 자동 삭제됨
        """
        # 1. 활성 주문(COOKING, COOKED, SERVING) 확인
        active_order_item = OrderItem.objects.filter(
            setmenu=set_menu,
            status__in=['COOKING', 'COOKED', 'SERVING']
        ).first()
        
        if active_order_item:
            raise ValidationError(
                f"현재 활성 주문(주문 ID: {active_order_item.order_id})에 포함되어 있습니다. 삭제할 수 없습니다."
            )
        
        # 2. 이미지 파일 삭제
        if set_menu.image:
            try:
                set_menu.image.delete(save=False)
            except Exception:
                pass  # 이미지 삭제 실패는 무시
        
        # 3. DB 레코드 삭제 (SetMenuItem은 CASCADE로 자동 삭제)
        set_menu.delete()
