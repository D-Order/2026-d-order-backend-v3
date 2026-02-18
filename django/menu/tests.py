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
