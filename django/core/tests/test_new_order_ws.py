"""
새 주문 생성 + WebSocket ADMIN_NEW_ORDER 알림 테스트 스크립트

사용법: Postman에서 WebSocket 연결한 상태로 이 스크립트를 실행하면
        ADMIN_NEW_ORDER 메시지가 실시간으로 수신됩니다.
"""
import os, sys, django

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'project.settings')
django.setup()

from django.utils import timezone
from table.models import TableUsage, Table
from menu.models import Menu
from cart.models import Cart
from order.models import Order, OrderItem
from booth.models import Booth
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync

booth = Booth.objects.get(pk=1)

# T6에 새 주문 생성
table = Table.objects.get(booth=booth, table_num=6)
now = timezone.now()

tu = TableUsage.objects.filter(table=table, ended_at__isnull=True).first()
if not tu:
    tu = TableUsage.objects.create(table=table, started_at=now)

try:
    cart = Cart.objects.get(table_usage=tu)
    cart.status = "ordered"
    cart.save(update_fields=["status"])
except Cart.DoesNotExist:
    cart = Cart(table_usage=tu, status="ordered", cart_price=0)
    cart.save()

menus = Menu.objects.filter(booth=booth).exclude(name="테이블 이용료")[:2]
total = 0
items_data = []
for m in menus:
    qty = 3
    total += int(m.price) * qty
    items_data.append((m, qty))

order = Order.objects.create(
    table_usage=tu,
    cart=cart,
    order_price=total,
    original_price=total,
    total_discount=0,
    order_status="PAID",
)

for m, qty in items_data:
    OrderItem.objects.create(
        order=order,
        menu=m,
        setmenu=None,
        parent=None,
        quantity=qty,
        fixed_price=int(m.price),
        status="COOKING",
    )

print(f"Order(id={order.pk}) T6 생성 완료! total={total:,}")

# WebSocket 그룹으로 ADMIN_NEW_ORDER 전송
channel_layer = get_channel_layer()
group_name = f"booth_{booth.pk}.order"

async_to_sync(channel_layer.group_send)(
    group_name,
    {
        "type": "admin_new_order",
        "data": {
            "order_id": order.pk,
        }
    }
)

print(f"ADMIN_NEW_ORDER 전송 완료! -> {group_name}")
print("Postman WebSocket에서 확인하세요!")
