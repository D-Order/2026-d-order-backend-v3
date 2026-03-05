import django
import os
import sys
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.join(current_dir, "..")
sys.path.append(project_root)
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'project.settings')
django.setup()

from cart.models import Cart, CartItem
from table.models import TableUsage, Table
from django.utils import timezone
from menu.models import Menu
from order.models import Order, OrderItem

# 기존 테스트 데이터 초기화 (순서 중요: FK 관계)
print("🔄 기존 테스트 데이터 초기화...")
OrderItem.objects.filter(order__cart_id=1).delete()
Order.objects.filter(cart_id=1).delete()
CartItem.objects.filter(cart_id=1).delete()
Cart.objects.filter(id=1).delete()

# 1. 메뉴 생성
menu, _ = Menu.objects.get_or_create(id=1, defaults={
    "name": "불고기피자", "price": 12000, "booth_id": 1
})
print(f"  Menu: {menu}")

# 2. 테이블
table, _ = Table.objects.get_or_create(id=1, defaults={
    "table_num": 1, "booth_id": 1
})
print(f"  Table: {table}")

# 3. 테이블 사용 세션
table_usage, _ = TableUsage.objects.get_or_create(id=1, defaults={
    "table": table, "accumulated_amount": 0, "started_at": timezone.now()
})
print(f"  TableUsage: {table_usage}")

# 4. 장바구니 (pending_payment 상태로 생성 - 결제 요청 중 상태)
cart = Cart.objects.create(
    id=1,
    status=Cart.Status.PENDING,
    table_usage=table_usage,
    cart_price=12000,
)
print(f"  Cart: {cart}")

# 5. 장바구니 아이템
cart_item = CartItem.objects.create(
    cart=cart, menu=menu, quantity=1, price_at_cart=12000,
)
print(f"  CartItem: {cart_item}")

print("")
print("✅ 테스트 객체 생성 완료!")
print(f"   Cart.status = {cart.status}")
print(f"   CartItem 수: {CartItem.objects.filter(cart=cart).count()}")
print("")
print("🧪 테스트 방법:")
print("  1) python manage.py listen_redis  (터미널 1)")
print("  2) python core/test_publish_order_event_for_listen_redis.py 1 new    (주문 생성)")
print("  3) python core/test_publish_order_event_for_listen_redis.py 1 cancel (결제거절 → Cart 복구)")
print("")
print("📌 결제거절 테스트는 Cart.status가 pending_payment일 때만 동작합니다.")
print("   주문 생성 후 결제거절을 테스트하려면 이 스크립트를 다시 실행하세요.")
