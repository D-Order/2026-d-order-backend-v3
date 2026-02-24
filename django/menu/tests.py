# 사용자 메뉴판 조회 API 테스트 (UserMenuListAPIView)

from django.test import override_settings
from rest_framework.test import APITestCase
from rest_framework import status
from table.models import Table, TableUsage
from menu.models import SetMenu
from django.utils import timezone
from core.test_utils import IN_MEMORY_STORAGES

@override_settings(STORAGES=IN_MEMORY_STORAGES)
class UserMenuListAPITest(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='testuser', password='testpass123')
        self.booth = Booth.objects.create(
            user=self.user,
            name='테스트부스',
            table_max_cnt=10,
            account='1234567890',
            depositor='홍길동',
            bank='신한은행',
            seat_type='PP',
            seat_fee_person=8000,
            seat_fee_table=0,
            table_limit_hours=2.0
        )
        self.table = Table.objects.create(booth=self.booth, table_num=3)
        self.menu = Menu.objects.create(booth=self.booth, name='피자', category='MENU', price=20000, stock=5)
        self.setmenu = SetMenu.objects.create(booth=self.booth, name='A세트', price=30000, description='세트 메뉴', image=None)
        self.usage = TableUsage.objects.create(table=self.table, started_at=timezone.now())
        self.url = f'/api/v3/django/booth/{self.booth.pk}/menu-list/'

    def test_menu_list_without_table_num(self):
        """table_num 없이 메뉴판 조회시 table_info 미포함, 메뉴 데이터만 반환"""
        resp = self.client.get(self.url)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertIn('data', resp.data)
        self.assertNotIn('table_info', resp.data)
        self.assertIn('FEE', resp.data['data'])
        self.assertIn('MENU', resp.data['data'])

    def test_menu_list_with_valid_table_num(self):
        """유효한 table_num으로 조회시 table_info 포함, usage id 포함"""
        resp = self.client.get(self.url + '?table_num=3')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertIn('table_info', resp.data)
        self.assertEqual(resp.data['table_info']['table_number'], 3)
        self.assertEqual(resp.data['table_info']['table_usage_id'], self.usage.id)
        self.assertIn('FEE', resp.data['data'])
        self.assertIn('MENU', resp.data['data'])

    def test_menu_list_with_invalid_table_num(self):
        """존재하지 않는 table_num으로 조회시 404 반환"""
        resp = self.client.get(self.url + '?table_num=999')
        self.assertEqual(resp.status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(resp.data['code'], 'TABLE_NOT_FOUND')

    def test_menu_list_with_invalid_table_num_type(self):
        """숫자가 아닌 table_num으로 조회시 400 반환"""
        resp = self.client.get(self.url + '?table_num=abc')
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(resp.data['code'], 'TABLE_NUMBER_INVALID')
import io
from PIL import Image

from django.test import override_settings
from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from rest_framework.test import APITestCase
from rest_framework import status

from booth.models import Booth
from menu.models import Menu, SetMenu, SetMenuItem
from core.test_utils import IN_MEMORY_STORAGES, suppress_request_warnings


def create_test_image(size=(100, 100), format='JPEG'):
    """테스트용 이미지 생성 (SimpleUploadedFile 반환)"""
    image = Image.new('RGB', size, color='red')
    buffer = io.BytesIO()
    image.save(buffer, format=format)
    buffer.seek(0)
    return SimpleUploadedFile(
        name='test_image.jpg',
        content=buffer.read(),
        content_type='image/jpeg'
    )


@override_settings(STORAGES=IN_MEMORY_STORAGES)
class MenuCreateAPITest(APITestCase):
    """메뉴 등록 API 테스트 (POST /api/v3/django/booth/menus/)"""
    
    def setUp(self):
        """테스트 데이터 설정"""
        self.url = '/api/v3/django/booth/menus/'
        
        # 유저 및 부스 생성
        self.user = User.objects.create_user(username='testuser', password='testpass123')
        self.booth = Booth.objects.create(
            user=self.user,
            name='테스트 부스',
            table_max_cnt=10,
            account='1234567890',
            depositor='홍길동',
            bank='신한은행',
            seat_type='NO',
            seat_fee_person=0,
            seat_fee_table=0,
            table_limit_hours=2.0
        )
        
        # 다른 유저/부스 (권한 테스트용)
        self.other_user = User.objects.create_user(username='otheruser', password='otherpass123')
        self.other_booth = Booth.objects.create(
            user=self.other_user,
            name='다른 부스',
            table_max_cnt=5,
            account='9876543210',
            depositor='김철수',
            bank='국민은행',
            seat_type='NO',
            seat_fee_person=0,
            seat_fee_table=0,
            table_limit_hours=1.0
        )
        
        self.valid_data = {
            'name': '아메리카노',
            'category': 'DRINK',
            'description': '시원한 아메리카노',
            'price': 4500,
            'stock': 100
        }
    
    # ==================== 성공 테스트 ====================
    
    def test_create_menu_success(self):
        """메뉴 등록 성공"""
        self.client.force_authenticate(user=self.user)
        
        response = self.client.post(self.url, self.valid_data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['message'], '메뉴 등록 성공')
        self.assertEqual(response.data['data']['name'], '아메리카노')
        self.assertEqual(response.data['data']['booth_id'], self.booth.pk)
        self.assertTrue(Menu.objects.filter(name='아메리카노', booth=self.booth).exists())
    
    def test_create_menu_with_image_success(self):
        """이미지 포함 메뉴 등록 성공"""
        self.client.force_authenticate(user=self.user)
        
        data = self.valid_data.copy()
        data['image'] = create_test_image()
        
        response = self.client.post(self.url, data, format='multipart')
        
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        menu = Menu.objects.get(name='아메리카노')
        self.assertTrue(menu.image)
    
    def test_create_menu_minimal_data(self):
        """필수 필드만으로 메뉴 등록 성공"""
        self.client.force_authenticate(user=self.user)
        
        minimal_data = {
            'name': '물',
            'category': 'MENU',
            'price': 0,
            'stock': 0
        }
        
        response = self.client.post(self.url, minimal_data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['data']['category'], 'MENU')
    
    def test_create_menu_category_menu(self):
        """카테고리 MENU로 등록"""
        self.client.force_authenticate(user=self.user)
        
        data = self.valid_data.copy()
        data['category'] = 'MENU'
        data['name'] = '김치찌개'
        
        response = self.client.post(self.url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['data']['category'], 'MENU')
    
    # ==================== 인증 실패 테스트 ====================
    
    def test_create_menu_unauthorized(self):
        """비로그인 시 401"""
        with suppress_request_warnings():
            response = self.client.post(self.url, self.valid_data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
    
    # ==================== 유효성 검사 실패 테스트 ====================
    
    def test_create_menu_missing_name(self):
        """name 누락 시 400"""
        self.client.force_authenticate(user=self.user)
        
        data = self.valid_data.copy()
        del data['name']
        
        with suppress_request_warnings():
            response = self.client.post(self.url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('name', response.data.get('errors', {}))
    
    def test_create_menu_missing_price(self):
        """price 누락 시 400"""
        self.client.force_authenticate(user=self.user)
        
        data = self.valid_data.copy()
        del data['price']
        
        with suppress_request_warnings():
            response = self.client.post(self.url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('price', response.data.get('errors', {}))
    
    def test_create_menu_negative_price(self):
        """음수 가격 시 400"""
        self.client.force_authenticate(user=self.user)
        
        data = self.valid_data.copy()
        data['price'] = -1000
        
        with suppress_request_warnings():
            response = self.client.post(self.url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
    
    def test_create_menu_negative_stock(self):
        """음수 재고 시 400"""
        self.client.force_authenticate(user=self.user)
        
        data = self.valid_data.copy()
        data['stock'] = -10
        
        with suppress_request_warnings():
            response = self.client.post(self.url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
    
    def test_create_menu_invalid_category(self):
        """잘못된 카테고리 시 400"""
        self.client.force_authenticate(user=self.user)
        
        data = self.valid_data.copy()
        data['category'] = 'INVALID'
        
        with suppress_request_warnings():
            response = self.client.post(self.url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
    
    def test_create_menu_name_too_long(self):
        """이름 20자 초과 시 400"""
        self.client.force_authenticate(user=self.user)
        
        data = self.valid_data.copy()
        data['name'] = 'a' * 21
        
        with suppress_request_warnings():
            response = self.client.post(self.url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
    
    def test_create_menu_description_too_long(self):
        """설명 30자 초과 시 400"""
        self.client.force_authenticate(user=self.user)
        
        data = self.valid_data.copy()
        data['description'] = 'a' * 31
        
        with suppress_request_warnings():
            response = self.client.post(self.url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)


@override_settings(STORAGES=IN_MEMORY_STORAGES)
class MenuUpdateAPITest(APITestCase):
    """메뉴 수정 API 테스트 (PATCH /api/v3/django/booth/menus/{menu_id}/)"""
    
    def setUp(self):
        """테스트 데이터 설정"""
        # 유저 및 부스 생성
        self.user = User.objects.create_user(username='testuser', password='testpass123')
        self.booth = Booth.objects.create(
            user=self.user,
            name='테스트 부스',
            table_max_cnt=10,
            account='1234567890',
            depositor='홍길동',
            bank='신한은행',
            seat_type='NO',
            seat_fee_person=0,
            seat_fee_table=0,
            table_limit_hours=2.0
        )
        
        # 테스트용 메뉴 생성
        self.menu = Menu.objects.create(
            booth=self.booth,
            name='아메리카노',
            category='DRINK',
            description='시원한 아메리카노',
            price=4500,
            stock=100
        )
        
        self.url = f'/api/v3/django/booth/menus/{self.menu.id}/'
        
        # 다른 유저/부스 (권한 테스트용)
        self.other_user = User.objects.create_user(username='otheruser', password='otherpass123')
        self.other_booth = Booth.objects.create(
            user=self.other_user,
            name='다른 부스',
            table_max_cnt=5,
            account='9876543210',
            depositor='김철수',
            bank='국민은행',
            seat_type='NO',
            seat_fee_person=0,
            seat_fee_table=0,
            table_limit_hours=1.0
        )
    
    # ==================== 성공 테스트 ====================
    
    def test_update_menu_price_success(self):
        """가격 수정 성공"""
        self.client.force_authenticate(user=self.user)
        
        response = self.client.patch(self.url, {'price': 5000}, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['message'], '메뉴 수정 성공')
        self.menu.refresh_from_db()
        self.assertEqual(self.menu.price, 5000)
    
    def test_update_menu_stock_success(self):
        """재고 수정 성공"""
        self.client.force_authenticate(user=self.user)
        
        response = self.client.patch(self.url, {'stock': 50}, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.menu.refresh_from_db()
        self.assertEqual(self.menu.stock, 50)
    
    def test_update_menu_multiple_fields(self):
        """여러 필드 동시 수정"""
        self.client.force_authenticate(user=self.user)
        
        data = {
            'name': '아이스 아메리카노',
            'price': 5000,
            'stock': 80
        }
        
        response = self.client.patch(self.url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.menu.refresh_from_db()
        self.assertEqual(self.menu.name, '아이스 아메리카노')
        self.assertEqual(self.menu.price, 5000)
        self.assertEqual(self.menu.stock, 80)
    
    def test_update_menu_stock_to_zero_soldout(self):
        """재고 0으로 수정 시 품절 표시"""
        self.client.force_authenticate(user=self.user)
        
        response = self.client.patch(self.url, {'stock': 0}, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data['data']['is_soldout'])
    
    def test_update_menu_delete_image(self):
        """이미지 삭제"""
        self.client.force_authenticate(user=self.user)
        
        # 먼저 이미지 설정
        self.menu.image = create_test_image()
        self.menu.save()
        
        response = self.client.patch(self.url, {'image_delete': True}, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.menu.refresh_from_db()
        self.assertFalse(self.menu.image)
    
    # ==================== 인증/권한 실패 테스트 ====================
    
    def test_update_menu_unauthorized(self):
        """비로그인 시 401"""
        with suppress_request_warnings():
            response = self.client.patch(self.url, {'price': 5000}, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
    
    def test_update_menu_forbidden(self):
        """다른 부스 메뉴 수정 시 403"""
        self.client.force_authenticate(user=self.other_user)
        
        with suppress_request_warnings():
            response = self.client.patch(self.url, {'price': 5000}, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(response.data['code'], 'PERMISSION_DENIED')
    
    def test_update_menu_not_found(self):
        """존재하지 않는 메뉴 수정 시 404"""
        self.client.force_authenticate(user=self.user)
        
        with suppress_request_warnings():
            response = self.client.patch('/api/v3/django/booth/menus/99999/', {'price': 5000}, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(response.data['code'], 'MENU_NOT_FOUND')
    
    # ==================== 유효성 검사 실패 테스트 ====================
    
    def test_update_menu_negative_price(self):
        """음수 가격 수정 시 400"""
        self.client.force_authenticate(user=self.user)
        
        with suppress_request_warnings():
            response = self.client.patch(self.url, {'price': -1000}, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
    
    def test_update_menu_negative_stock(self):
        """음수 재고 수정 시 400"""
        self.client.force_authenticate(user=self.user)
        
        with suppress_request_warnings():
            response = self.client.patch(self.url, {'stock': -10}, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)


@override_settings(STORAGES=IN_MEMORY_STORAGES)
class MenuDeleteAPITest(APITestCase):
    """메뉴 삭제 API 테스트 (DELETE /api/v3/django/booth/menus/{menu_id}/)"""
    
    def setUp(self):
        """테스트 데이터 설정"""
        # 유저 및 부스 생성
        self.user = User.objects.create_user(username='testuser', password='testpass123')
        self.booth = Booth.objects.create(
            user=self.user,
            name='테스트 부스',
            table_max_cnt=10,
            account='1234567890',
            depositor='홍길동',
            bank='신한은행',
            seat_type='NO',
            seat_fee_person=0,
            seat_fee_table=0,
            table_limit_hours=2.0
        )
        
        # 테스트용 메뉴 생성
        self.menu = Menu.objects.create(
            booth=self.booth,
            name='삭제할 메뉴',
            category='MENU',
            price=10000,
            stock=50
        )
        
        self.url = f'/api/v3/django/booth/menus/{self.menu.id}/'
        
        # 다른 유저/부스 (권한 테스트용)
        self.other_user = User.objects.create_user(username='otheruser', password='otherpass123')
        self.other_booth = Booth.objects.create(
            user=self.other_user,
            name='다른 부스',
            table_max_cnt=5,
            account='9876543210',
            depositor='김철수',
            bank='국민은행',
            seat_type='NO',
            seat_fee_person=0,
            seat_fee_table=0,
            table_limit_hours=1.0
        )
    
    # ==================== 성공 테스트 ====================
    
    def test_delete_menu_success(self):
        """메뉴 삭제 성공"""
        self.client.force_authenticate(user=self.user)
        menu_id = self.menu.id
        
        response = self.client.delete(self.url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['message'], '메뉴 삭제 성공')
        self.assertEqual(response.data['data']['menu_id'], menu_id)
        self.assertFalse(Menu.objects.filter(id=menu_id).exists())
    
    def test_delete_menu_with_image(self):
        """이미지가 있는 메뉴 삭제 시 이미지도 삭제"""
        self.client.force_authenticate(user=self.user)
        
        # 이미지 설정
        self.menu.image = create_test_image()
        self.menu.save()
        
        response = self.client.delete(self.url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertFalse(Menu.objects.filter(id=self.menu.id).exists())
    
    # ==================== 인증/권한 실패 테스트 ====================
    
    def test_delete_menu_unauthorized(self):
        """비로그인 시 401"""
        with suppress_request_warnings():
            response = self.client.delete(self.url)
        
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
    
    def test_delete_menu_forbidden(self):
        """다른 부스 메뉴 삭제 시 403"""
        self.client.force_authenticate(user=self.other_user)
        
        with suppress_request_warnings():
            response = self.client.delete(self.url)
        
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(response.data['code'], 'PERMISSION_DENIED')
        self.assertIn('삭제', response.data['message'])
    
    def test_delete_menu_not_found(self):
        """존재하지 않는 메뉴 삭제 시 404"""
        self.client.force_authenticate(user=self.user)
        
        with suppress_request_warnings():
            response = self.client.delete('/api/v3/django/booth/menus/99999/')
        
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(response.data['code'], 'MENU_NOT_FOUND')
        self.assertIn('삭제', response.data['message'])
    
    # ==================== 중복 삭제 테스트 ====================
    
    def test_delete_menu_twice(self):
        """이미 삭제된 메뉴 다시 삭제 시 404"""
        self.client.force_authenticate(user=self.user)
        
        # 첫 번째 삭제
        response = self.client.delete(self.url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # 두 번째 삭제 시도
        with suppress_request_warnings():
            response = self.client.delete(self.url)
        
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)


@override_settings(STORAGES=IN_MEMORY_STORAGES)
class SetMenuAPITest(APITestCase):
    """세트메뉴 등록/수정/삭제 API 통합 테스트"""
    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_user(username='setuser', password='setpass123')
        cls.booth = Booth.objects.create(
            user=cls.user,
            name='세트부스',
            table_max_cnt=5,
            account='111222333',
            depositor='세트주인',
            bank='카카오',
            seat_type='NO',
            seat_fee_person=0,
            seat_fee_table=0,
            table_limit_hours=1.0
        )
        cls.menu1 = Menu.objects.create(booth=cls.booth, name='단품1', category='MENU', price=1000, stock=10)
        cls.menu2 = Menu.objects.create(booth=cls.booth, name='단품2', category='MENU', price=2000, stock=5)
        cls.menu3 = Menu.objects.create(booth=cls.booth, name='단품3', category='MENU', price=3000, stock=0)
        cls.other_user = User.objects.create_user(username='otheruser', password='otherpass123')
        cls.other_booth = Booth.objects.create(
            user=cls.other_user,
            name='다른부스',
            table_max_cnt=3,
            account='444555666',
            depositor='다른주인',
            bank='농협',
            seat_type='NO',
            seat_fee_person=0,
            seat_fee_table=0,
            table_limit_hours=1.0
        )
        cls.other_menu = Menu.objects.create(booth=cls.other_booth, name='외부메뉴', category='MENU', price=5000, stock=10)

    def setUp(self):
        self.client.force_authenticate(user=self.user)
        self.url = '/api/v3/django/booth/sets/'

    def test_setmenu_create_success(self):
        """세트메뉴 등록 성공"""
        data = {
            'name': '세트1',
            'description': '맛있는 세트',
            'price': 5000,
            'set_items': [
                {'menu_id': self.menu1.id, 'quantity': 2},
                {'menu_id': self.menu2.id, 'quantity': 1}
            ]
        }
        response = self.client.post(self.url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['message'], '세트메뉴 등록 성공')
        self.assertEqual(response.data['data']['name'], '세트1')
        self.assertEqual(len(response.data['data']['set_items']), 2)

    def test_setmenu_create_with_image(self):
        """이미지 포함 세트메뉴 등록 성공"""
        import json
        data = {
            'name': '세트2',
            'description': '이미지세트',
            'price': 8000,
            'set_items': json.dumps([
                {'menu_id': self.menu1.id, 'quantity': 1}
            ]),
            'image': create_test_image()
        }
        response = self.client.post(self.url, data, format='multipart')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertTrue(response.data['data']['image'])

    def test_setmenu_create_minimal(self):
        """필수값만으로 세트메뉴 등록 성공"""
        data = {
            'name': '세트3',
            'price': 1000,
            'set_items': [
                {'menu_id': self.menu1.id}
            ]
        }
        response = self.client.post(self.url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['data']['name'], '세트3')

    def test_setmenu_create_invalid_menu(self):
        """존재하지 않는 menu_id 포함 시 400"""
        data = {
            'name': '세트4',
            'price': 1000,
            'set_items': [
                {'menu_id': 99999}
            ]
        }
        with suppress_request_warnings():
            response = self.client.post(self.url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('set_items', response.data.get('errors', {}))

    def test_setmenu_create_empty_items(self):
        """set_items 빈 배열 시 400"""
        data = {
            'name': '세트5',
            'price': 1000,
            'set_items': []
        }
        with suppress_request_warnings():
            response = self.client.post(self.url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('set_items', response.data.get('errors', {}))

    def test_setmenu_create_unauthorized(self):
        """비로그인 시 401"""
        self.client.force_authenticate(user=None)
        data = {
            'name': '세트6',
            'price': 1000,
            'set_items': [{'menu_id': self.menu1.id}]
        }
        with suppress_request_warnings():
            response = self.client.post(self.url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_setmenu_update_success(self):
        """세트메뉴 수정 성공 (이름/구성/가격 변경)"""
        # 등록
        setmenu = SetMenu.objects.create(booth=self.booth, name='수정세트', price=1000)
        SetMenuItem.objects.create(set_menu=setmenu, menu=self.menu1, quantity=1)
        url = f'/api/v3/django/booth/sets/{setmenu.id}/'
        patch_data = {
            'name': '수정된세트',
            'price': 2000,
            'set_items': [
                {'menu_id': self.menu2.id, 'quantity': 2}
            ]
        }
        response = self.client.patch(url, patch_data, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['data']['name'], '수정된세트')
        self.assertEqual(len(response.data['data']['set_items']), 1)
        self.assertEqual(response.data['data']['set_items'][0]['menu_id'], self.menu2.id)

    def test_setmenu_update_partial(self):
        """세트메뉴 부분 수정 (이름만)"""
        setmenu = SetMenu.objects.create(booth=self.booth, name='부분수정', price=1000)
        SetMenuItem.objects.create(set_menu=setmenu, menu=self.menu1, quantity=1)
        url = f'/api/v3/django/booth/sets/{setmenu.id}/'
        patch_data = {'name': '이름만수정'}
        response = self.client.patch(url, patch_data, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['data']['name'], '이름만수정')

    def test_setmenu_update_image_delete(self):
        """세트메뉴 이미지 삭제"""
        setmenu = SetMenu.objects.create(booth=self.booth, name='이미지세트', price=1000)
        setmenu.image = create_test_image()
        setmenu.save()
        SetMenuItem.objects.create(set_menu=setmenu, menu=self.menu1, quantity=1)
        url = f'/api/v3/django/booth/sets/{setmenu.id}/'
        patch_data = {'image_delete': True}
        response = self.client.patch(url, patch_data, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        setmenu.refresh_from_db()
        self.assertFalse(setmenu.image)

    def test_setmenu_update_forbidden(self):
        """다른 부스 세트메뉴 수정 시 403"""
        setmenu = SetMenu.objects.create(booth=self.other_booth, name='외부세트', price=1000)
        SetMenuItem.objects.create(set_menu=setmenu, menu=self.other_menu, quantity=1)
        url = f'/api/v3/django/booth/sets/{setmenu.id}/'
        patch_data = {'name': '수정시도'}
        response = self.client.patch(url, patch_data, format='json')
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(response.data['code'], 'PERMISSION_DENIED')

    def test_setmenu_update_not_found(self):
        """존재하지 않는 세트메뉴 수정 시 404"""
        url = '/api/v3/django/booth/sets/99999/'
        patch_data = {'name': '없는세트'}
        response = self.client.patch(url, patch_data, format='json')
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(response.data['code'], 'MENU_NOT_FOUND')

    def test_setmenu_delete_success(self):
        """세트메뉴 삭제 성공"""
        setmenu = SetMenu.objects.create(booth=self.booth, name='삭제세트', price=1000)
        SetMenuItem.objects.create(set_menu=setmenu, menu=self.menu1, quantity=1)
        url = f'/api/v3/django/booth/sets/{setmenu.id}/'
        response = self.client.delete(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertFalse(SetMenu.objects.filter(id=setmenu.id).exists())
        self.assertFalse(SetMenuItem.objects.filter(set_menu_id=setmenu.id).exists())

    def test_setmenu_delete_forbidden(self):
        """다른 부스 세트메뉴 삭제 시 403"""
        setmenu = SetMenu.objects.create(booth=self.other_booth, name='외부세트', price=1000)
        SetMenuItem.objects.create(set_menu=setmenu, menu=self.other_menu, quantity=1)
        url = f'/api/v3/django/booth/sets/{setmenu.id}/'
        response = self.client.delete(url)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(response.data['code'], 'PERMISSION_DENIED')

    def test_setmenu_delete_not_found(self):
        """존재하지 않는 세트메뉴 삭제 시 404"""
        url = '/api/v3/django/booth/sets/99999/'
        response = self.client.delete(url)
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(response.data['code'], 'MENU_NOT_FOUND')

    def test_setmenu_delete_twice(self):
        """이미 삭제된 세트메뉴 다시 삭제 시 404"""
        setmenu = SetMenu.objects.create(booth=self.booth, name='삭제2회', price=1000)
        SetMenuItem.objects.create(set_menu=setmenu, menu=self.menu1, quantity=1)
        url = f'/api/v3/django/booth/sets/{setmenu.id}/'
        response = self.client.delete(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        response2 = self.client.delete(url)
        self.assertEqual(response2.status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(response2.data['code'], 'MENU_NOT_FOUND')

    def test_setmenu_soldout_logic(self):
        """구성 메뉴 중 하나라도 품절이면 is_soldout True"""
        setmenu = SetMenu.objects.create(booth=self.booth, name='품절세트', price=1000)
        SetMenuItem.objects.create(set_menu=setmenu, menu=self.menu3, quantity=1)  # stock=0
        url = f'/api/v3/django/booth/sets/{setmenu.id}/'
        response = self.client.patch(url, {'name': '품절세트수정'}, format='json')
        self.assertTrue(response.data['data']['is_soldout'])

    def test_setmenu_origin_price(self):
        """origin_price 계산 검증"""
        setmenu = SetMenu.objects.create(booth=self.booth, name='원가세트', price=1000)
        SetMenuItem.objects.create(set_menu=setmenu, menu=self.menu1, quantity=2)  # 1000*2
        SetMenuItem.objects.create(set_menu=setmenu, menu=self.menu2, quantity=1)  # 2000*1
        url = f'/api/v3/django/booth/sets/{setmenu.id}/'
        response = self.client.patch(url, {'name': '원가세트수정'}, format='json')
        self.assertEqual(response.data['data']['origin_price'], 4000)

    def test_setmenu_update_invalid_items(self):
        """set_items 잘못된 값(빈배열) 시 400"""
        setmenu = SetMenu.objects.create(booth=self.booth, name='잘못세트', price=1000)
        SetMenuItem.objects.create(set_menu=setmenu, menu=self.menu1, quantity=1)
        url = f'/api/v3/django/booth/sets/{setmenu.id}/'
        patch_data = {'set_items': []}
        response = self.client.patch(url, patch_data, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('set_items', response.data.get('errors', {}))

    def test_setmenu_update_invalid_menu(self):
        """set_items에 없는 menu_id 포함 시 400"""
        setmenu = SetMenu.objects.create(booth=self.booth, name='잘못세트2', price=1000)
        SetMenuItem.objects.create(set_menu=setmenu, menu=self.menu1, quantity=1)
        url = f'/api/v3/django/booth/sets/{setmenu.id}/'
        patch_data = {'set_items': [{'menu_id': 99999}]}
        response = self.client.patch(url, patch_data, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('set_items', response.data.get('errors', {}))

    def test_setmenu_update_image_modify_forbidden(self):
        """이미지 직접 수정 시도 시 400"""
        setmenu = SetMenu.objects.create(booth=self.booth, name='이미지수정불가', price=1000)
        SetMenuItem.objects.create(set_menu=setmenu, menu=self.menu1, quantity=1)
        url = f'/api/v3/django/booth/sets/{setmenu.id}/'
        patch_data = {'image': create_test_image()}
        response = self.client.patch(url, patch_data, format='multipart')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('image', response.data.get('errors', {}))

    # 기타 추가 검증 필요시 여기에 작성


class MenuModelTest(APITestCase):
    """Menu 모델 테스트"""
    
    def setUp(self):
        self.user = User.objects.create_user(username='testuser', password='testpass123')
        self.booth = Booth.objects.create(
            user=self.user,
            name='테스트 부스',
            table_max_cnt=10,
            account='1234567890',
            depositor='홍길동',
            bank='신한은행',
            seat_type='NO',
            seat_fee_person=0,
            seat_fee_table=0,
            table_limit_hours=2.0
        )
    
    def test_menu_str(self):
        """Menu __str__ 테스트"""
        menu = Menu.objects.create(
            booth=self.booth,
            name='테스트 메뉴',
            price=5000
        )
        
        self.assertEqual(str(menu), '[테스트 부스] 테스트 메뉴')
    
    def test_menu_default_category(self):
        """카테고리 기본값 MENU"""
        menu = Menu.objects.create(
            booth=self.booth,
            name='테스트 메뉴',
            price=5000
        )
        
        self.assertEqual(menu.category, 'MENU')
    
    def test_menu_default_stock(self):
        """재고 기본값 0"""
        menu = Menu.objects.create(
            booth=self.booth,
            name='테스트 메뉴',
            price=5000
        )
        
        self.assertEqual(menu.stock, 0)
    
    def test_menu_cascade_delete_with_booth(self):
        """부스 삭제 시 메뉴도 삭제 (CASCADE)"""
        Menu.objects.create(
            booth=self.booth,
            name='테스트 메뉴',
            price=5000
        )
        
        self.booth.delete()
        
        self.assertEqual(Menu.objects.count(), 0)
