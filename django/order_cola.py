#!/usr/bin/env python
"""콜라 1개 주문 생성"""
import os
import django
import uuid

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'project.settings')
django.setup()

from order.services import OrderService
from table.models import Table, TableUsage
from cart.models import Cart, CartItem
from menu.models import Menu
from booth.models import Booth
from django.utils import timezone

print("[주문] 콜라 1개 주문하기")
print("=" * 70)

try:
    # 1. 부스 조회
    booth = Booth.objects.first()
    print(f"✅ 부스: {booth.name}")

    # 2. 콜라 메뉴 조회
    cola = Menu.objects.filter(booth=booth, name__contains="콜라").first()
    if not cola:
        print("❌ 콜라 메뉴를 찾을 수 없습니다")
        exit(1)
    print(f"✅ 메뉴: {cola.name} ({cola.price:,}원)")

    # 3. 새 테이블 생성
    import time
    test_table_num = 6000 + int(time.time()) % 1000
    table = Table.objects.create(booth=booth, table_num=test_table_num, status="AVAILABLE")
    print(f"✅ 테이블: {table.table_num}번")

    # 4. TableUsage 생성
    usage = TableUsage.objects.create(table=table, started_at=timezone.now())
    print(f"✅ TableUsage: ID {usage.pk}")

    # 5. Cart 생성
    cart = Cart.objects.create(table_usage=usage, status="active", cart_price=cola.price)
    print(f"✅ 장바구니: ID {cart.pk}")

    # 6. CartItem 생성
    cart_item = CartItem.objects.create(
        cart=cart,
        menu=cola,
        quantity=1,
        price_at_cart=cola.price
    )
    print(f"✅ 주문 항목: {cola.name} x1")

    # 7. 주문 생성
    print("\n[주문 생성]")
    event_data = {
        "event_id": str(uuid.uuid4()),
        "data": {
            "cart_id": cart.pk,
            "table_usage_id": usage.pk,
            "status": "completed",
            "order_items": [{"type": "menu", "menu_id": cola.pk, "quantity": 1, "price_at_cart": cola.price}],
            "total_price": cola.price,
            "original_total_price": cola.price,
            "total_discount": 0,
        }
    }

    result = OrderService.create_order_from_event(event_data)
    
    if result.get('result') == 'success':
        order_id = result.get('order_id')
        print(f"✅ 주문 성공! Order ID: {order_id}")
        print(f"   테이블: {table.table_num}번")
        print(f"   메뉴: {cola.name}")
        print(f"   가격: {cola.price:,}원")
        print(f"\n🎉 WebSocket으로 운영자 대시보드에 실시간 전송됨!")
    else:
        print(f"⚠️ 결과: {result}")

except Exception as e:
    print(f"❌ 오류: {e}")
    import traceback
    traceback.print_exc()
