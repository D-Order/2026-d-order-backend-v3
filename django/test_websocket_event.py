#!/usr/bin/env python
"""
admin_new_order WebSocket 이벤트 테스트
새로운 테이블을 생성하고 주문 이벤트를 발행해서 group_send가 작동하는지 확인
"""
import os
import sys
import django
import uuid
from datetime import datetime

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'project.settings')
os.environ.setdefault('DJANGO_ENV', 'test')
django.setup()

from order.services import OrderService
from table.models import Table, TableUsage
from cart.models import Cart, CartItem
from menu.models import Menu
from booth.models import Booth
from django.utils import timezone

print("[테스트 시작] admin_new_order WebSocket 이벤트 검증")
print("=" * 70)

try:
    # 1. Booth 조회
    booth = Booth.objects.first()
    if not booth:
        print("❌ Booth가 없습니다")
        sys.exit(1)
    print(f"✅ Booth 조회: {booth.name} (ID: {booth.pk})")

    # 2. 새로운 Table 생성 (테스트용)
    import time
    test_table_num = 9000 + int(time.time()) % 1000  # 현재 시간기반 고유 번호
    
    table = Table.objects.create(
        booth=booth,
        table_num=test_table_num,
        status="AVAILABLE"
    )
    print(f"✅ Table 생성: {table.table_num}번 (ID: {table.pk})")

    # 3. TableUsage 생성
    usage = TableUsage.objects.create(
        table=table,
        started_at=timezone.now(),
    )
    print(f"✅ TableUsage 생성: (ID: {usage.pk})")

    # 4. Cart 생성
    cart = Cart.objects.create(
        table_usage=usage,
        status="active"
    )
    print(f"✅ Cart 생성: (ID: {cart.pk})")

    # 5. Menu 조회
    menu = Menu.objects.filter(booth=booth, category="MENU").exclude(category="FEE").first()
    if not menu:
        print("❌ Menu가 없습니다")
        sys.exit(1)
    print(f"✅ Menu 조회: {menu.name} (가격: {menu.price:,}원)")

    # 6. CartItem 생성
    cart_item = CartItem.objects.create(
        cart=cart,
        menu=menu,
        quantity=1,
        price_at_cart=menu.price
    )
    print(f"✅ CartItem 생성: {menu.name} x1 (type: {cart_item.type})")

    # 7. Cart 금액 업데이트
    cart.cart_price = menu.price
    cart.save()
    print(f"✅ Cart 금액: {cart.cart_price:,}원")

    # 8. 주문 생성 이벤트 발행
    print("\n[주문 생성 이벤트 발행]")
    print("-" * 70)

    # 이벤트 데이터 구성
    event_id = str(uuid.uuid4())
    event_data = {
        "event_id": event_id,
        "data": {
            "cart_id": cart.pk,
            "table_usage_id": usage.pk,
            "status": "completed",
            "order_items": [
                {
                    "type": "menu",
                    "menu_id": menu.pk,
                    "quantity": 1,
                    "price_at_cart": menu.price,
                }
            ],
            "order_price": cart.cart_price,
            "original_price": cart.cart_price,
            "total_price": cart.cart_price,  # 외부 이벤트에서 필요한 필드
            "original_total_price": cart.cart_price,
            "total_discount": 0,
        }
    }

    print(f"이벤트 데이터:")
    print(f"  - event_id: {event_id}")
    print(f"  - cart_id: {cart.pk}")
    print(f"  - table_usage_id: {usage.pk}")
    print(f"  - booth_id: {booth.pk}")
    print(f"  - menu: {menu.name}")
    print(f"  - order_price: {event_data['data']['order_price']:,}원")

    print(f"\n[OrderService.create_order_from_event 실행]")
    result = OrderService.create_order_from_event(event_data)
    
    if result.get('result') == 'success':
        print(f"✅ 주문 생성 성공!")
        print(f"  - Order ID: {result.get('order_id')}")
        print(f"\n🔍 Daphne 터미널에서 다음을 확인하세요:")
        print(f"  > '[WebSocket] group_send 시도: booth_{booth.pk}.order'")
        print(f"  > '[WebSocket] admin_new_order 전송 완료: order_id={result.get('order_id')}'")
        print(f"\n✨ 이 메시지가 보이면 WebSocket broadcasting이 작동한다는 뜻입니다!")
    else:
        print(f"⚠️ 주문 생성 결과: {result}")
        if result.get('result') == 'duplicate_cart':
            print(f"   (이미 해당 cart로 주문이 존재합니다)")

    print("\n" + "=" * 70)
    print("[테스트 완료]")

except Exception as e:
    print(f"❌ 오류 발생: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)
