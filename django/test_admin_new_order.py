#!/usr/bin/env python
"""
admin_new_order WebSocket 이벤트 테스트
실제 주문을 생성해서 group_send가 제대로 작동하는지 확인
"""
import os
import sys
import django
import uuid

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'project.settings')
os.environ.setdefault('DJANGO_ENV', 'test')
django.setup()

from django.test import TestCase
from order.services import OrderService
from table.models import Table, TableUsage
from cart.models import Cart, CartItem
from menu.models import Menu
from booth.models import Booth
from django.utils import timezone

print("[테스트 시작] admin_new_order 이벤트 검증")
print("=" * 60)

# 1. 테스트 데이터 조회 또는 생성
booth = Booth.objects.first()
if not booth:
    print("❌ Booth가 없습니다")
    sys.exit(1)
print(f"✅ Booth 조회: {booth.name}")

# 2. 테이블 조회
table = Table.objects.filter(booth=booth).first()
if not table:
    print("❌ Table이 없습니다")
    sys.exit(1)
print(f"✅ Table 조회: {table.table_num}번")

# 3. 활성 TableUsage 조회 또는 생성
usage = TableUsage.objects.filter(
    table=table,
    ended_at__isnull=True
).first()

if not usage:
    # 새로운 TableUsage 생성
    usage = TableUsage.objects.create(
        table=table,
        started_at=timezone.now(),
    )
    print(f"✅ TableUsage 생성: {usage.id}")
else:
    print(f"✅ TableUsage 조회: {usage.id}")

# 4. Cart 조회 또는 생성 (항상 새로운 cart 생성해서 테스트)
# 기존 cart가 있으면 삭제하고 새로 생성
Cart.objects.filter(table_usage=usage).delete()
cart = Cart.objects.create(
    table_usage=usage,
    status="active"
)
print(f"✅ Cart 생성: {cart.id}")

# 5. Menu 조회
menu = Menu.objects.filter(booth=booth, category="MENU").exclude(category="FEE").first()
if not menu:
    print("❌ Menu가 없습니다")
    sys.exit(1)
print(f"✅ Menu 조회: {menu.name}")

# 6. CartItem 추가 (없으면 추가)
cart_item = CartItem.objects.filter(cart=cart, menu=menu).first()
if not cart_item:
    cart_item = CartItem.objects.create(
        cart=cart,
        menu=menu,
        quantity=1,
        price_at_cart=menu.price
    )
    print(f"✅ CartItem 생성: {menu.name} x1")
else:
    print(f"✅ CartItem 존재: {menu.name} x{cart_item.quantity}")

# 7. Cart 금액 계산
cart.cart_price = menu.price
cart.save()
print(f"✅ Cart 금액 업데이트: {cart.cart_price:,}원")

# 8. 주문 생성 이벤트 발행
print("\n[주문 생성 이벤트 발행]")
print("-" * 60)

# Redis에서 발행하는 이벤트 구조 (listen_redis.py가 파싱하는 형태)
event_data = {
    "event_id": str(uuid.uuid4()),  # 유효한 UUID 생성
    "data": {
        "cart_id": cart.id,
        "table_usage_id": usage.id,
        "status": "completed",  # 중요: "completed"여야 함
        "order_items": [
            {
                "type": cart_item.type,
                "menu_id": cart_item.menu_id,
                "quantity": cart_item.quantity,
                "price_at_cart": cart_item.price_at_cart,
            }
        ],
        "order_price": cart.cart_price,
        "original_price": cart.cart_price,
        "total_discount": 0,
    }
}

print(f"이벤트 데이터:")
print(f"  - event_id: {event_data['event_id']}")
print(f"  - status: {event_data['data']['status']}")
print(f"  - cart_id: {event_data['data']['cart_id']}")
print(f"  - table_usage_id: {event_data['data']['table_usage_id']}")
print(f"  - booth_id: {booth.pk}")
print(f"  - order_items: {event_data['data']['order_items']}")
print(f"  - order_price: {event_data['data']['order_price']:,}원")

print("\n[OrderService.create_order_from_event 호출]")
try:
    result = OrderService.create_order_from_event(event_data)
    print(f"✅ 주문 생성 성공!")
    print(f"  - 결과: {result}")
    print(f"\n📝 Daphne 로그에서 다음을 확인하세요:")
    print(f"  - '[WebSocket] group_send 시도: booth_{booth.pk}.order'")
    print(f"  - '[WebSocket] admin_new_order 전송 완료: order_id=...'")
except Exception as e:
    print(f"❌ 주문 생성 실패: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

print("\n" + "=" * 60)
print("[테스트 완료]")
print("Daphne 터미널에서 로그를 확인하세요!")
