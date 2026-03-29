import pytest
from channels.testing import WebsocketCommunicator
from project.asgi import application
from django.contrib.auth import get_user_model
from asgiref.sync import sync_to_async
from channels.layers import get_channel_layer
from order.models import Order, OrderItem
from table.models import Table, TableUsage
from django.utils import timezone
import datetime

User = get_user_model()

async def create_order_with_items(user, status="PAID", coupon=False):
    from booth.models import Booth
    booth = await sync_to_async(Booth.objects.create)(user=user, name="테스트부스", account="123", bank="테스트은행", table_max_cnt=10, table_limit_hours=2)
    table = await sync_to_async(Table.objects.create)(booth=booth, table_num=1)
    table_usage = await sync_to_async(TableUsage.objects.create)(table=table, started_at=timezone.now())
    order = await sync_to_async(Order.objects.create)(order_price=10000, order_status=status, table_usage=table_usage)
    item = await sync_to_async(OrderItem.objects.create)(order=order, menu=1, quantity=2, fixed_price=5000, status="cooking")
    return order, item, table_usage

def get_time_ago(dt):
    diff = timezone.now() - dt
    minutes = int(diff.total_seconds() // 60)
    return f"{minutes}분 전"

@pytest.mark.asyncio
@pytest.mark.django_db(transaction=True)
async def test_admin_order_snapshot_message(settings):
    settings.CHANNEL_LAYERS = {
        "default": {
            "BACKEND": "channels.layers.InMemoryChannelLayer"
        }
    }
    user = await sync_to_async(User.objects.create_user)(username="admin_test", password="password")
    order, item, table_usage = await create_order_with_items(user)
    communicator = WebsocketCommunicator(application, "/ws/django/admin/orders/management/")
    communicator.scope["user"] = user
    connected, _ = await communicator.connect()
    assert connected
    response = await communicator.receive_json_from(timeout=2)
    assert response["type"] == "ADMIN_ORDER_SNAPSHOT"
    assert "orders" in response["data"]
    assert response["data"]["orders"][0]["order_id"] == order.id
    assert response["data"]["orders"][0]["table_num"] == 1
    assert response["data"]["orders"][0]["order_status"] == "PAID"
    assert response["data"]["orders"][0]["time_ago"].endswith("분 전")
    assert isinstance(response["data"]["orders"][0]["items"], list)
    await communicator.disconnect()

@pytest.mark.asyncio
@pytest.mark.django_db(transaction=True)
async def test_admin_new_order_message(settings):
    settings.CHANNEL_LAYERS = {
        "default": {
            "BACKEND": "channels.layers.InMemoryChannelLayer"
        }
    }
    user = await sync_to_async(User.objects.create_user)(username="admin_test2", password="password")
    order, item, table_usage = await create_order_with_items(user)
    communicator = WebsocketCommunicator(application, "/ws/django/admin/orders/management/")
    communicator.scope["user"] = user
    connected, _ = await communicator.connect()
    assert connected
    await communicator.receive_json_from(timeout=2)  # snapshot skip
    group_name = f"booth_{user.pk}.order"
    channel_layer = get_channel_layer()
    await channel_layer.group_send(
        group_name,
        {
            "type": "admin_new_order",
            "data": {"order": {
                "order_id": order.id,
                "table_num": 1,
                "table_usage_id": table_usage.id,
                "order_status": "PAID",
                "time_ago": get_time_ago(order.created_at),
                "has_coupon": False,
                "items": [{
                    "order_item_id": item.id,
                    "menu_name": "테스트메뉴",
                    "image": None,
                    "quantity": item.quantity,
                    "fixed_price": item.fixed_price,
                    "item_total_price": item.fixed_price * item.quantity,
                    "status": item.status,
                    "is_set": False
                }]
            }}
        }
    )
    response = await communicator.receive_json_from(timeout=2)
    assert response["type"] == "ADMIN_NEW_ORDER"
    assert isinstance(response["data"]["orders"], list)
    assert response["data"]["orders"][0]["order_id"] == order.id
    await communicator.disconnect()

@pytest.mark.asyncio
@pytest.mark.django_db(transaction=True)
async def test_admin_order_update_message(settings):
    settings.CHANNEL_LAYERS = {
        "default": {
            "BACKEND": "channels.layers.InMemoryChannelLayer"
        }
    }
    user = await sync_to_async(User.objects.create_user)(username="admin_test3", password="password")
    order, item, table_usage = await create_order_with_items(user)
    communicator = WebsocketCommunicator(application, "/ws/django/admin/orders/management/")
    communicator.scope["user"] = user
    connected, _ = await communicator.connect()
    assert connected
    await communicator.receive_json_from(timeout=2)
    group_name = f"booth_{user.pk}.order"
    channel_layer = get_channel_layer()
    await channel_layer.group_send(
        group_name,
        {
            "type": "admin_order_update",
            "data": {
                "order_id": order.id,
                "item": {
                    "id": item.id,
                    "status": "serving",
                    "is_all_served": False
                }
            }
        }
    )
    response = await communicator.receive_json_from(timeout=2)
    assert response["type"] == "ADMIN_ORDER_UPDATE"
    assert response["data"]["order_id"] == order.id
    assert response["data"]["item"]["id"] == item.id
    assert response["data"]["item"]["status"] == "serving"
    await communicator.disconnect()

@pytest.mark.asyncio
@pytest.mark.django_db(transaction=True)
async def test_admin_order_cancelled_message(settings):
    settings.CHANNEL_LAYERS = {
        "default": {
            "BACKEND": "channels.layers.InMemoryChannelLayer"
        }
    }
    user = await sync_to_async(User.objects.create_user)(username="admin_test4", password="password")
    order, item, table_usage = await create_order_with_items(user)
    communicator = WebsocketCommunicator(application, "/ws/django/admin/orders/management/")
    communicator.scope["user"] = user
    connected, _ = await communicator.connect()
    assert connected
    await communicator.receive_json_from(timeout=2)
    group_name = f"booth_{user.pk}.order"
    channel_layer = get_channel_layer()
    await channel_layer.group_send(
        group_name,
        {
            "type": "admin_order_cancelled",
            "data": {
                "order_id": order.id,
                "item_id": item.id,
                "refund_amount": 10000,
                "new_total_sales": 90000
            }
        }
    )
    response = await communicator.receive_json_from(timeout=2)
    assert response["type"] == "ADMIN_ORDER_CANCELLED"
    assert response["data"]["order_id"] == order.id
    assert response["data"]["item_id"] == item.id
    assert response["data"]["refund_amount"] == 10000
    assert response["data"]["new_total_sales"] == 90000
    await communicator.disconnect()

@pytest.mark.asyncio
@pytest.mark.django_db(transaction=True)
async def test_admin_order_completed_message(settings):
    settings.CHANNEL_LAYERS = {
        "default": {
            "BACKEND": "channels.layers.InMemoryChannelLayer"
        }
    }
    user = await sync_to_async(User.objects.create_user)(username="admin_test5", password="password")
    order, item, table_usage = await create_order_with_items(user)
    communicator = WebsocketCommunicator(application, "/ws/django/admin/orders/management/")
    communicator.scope["user"] = user
    connected, _ = await communicator.connect()
    assert connected
    await communicator.receive_json_from(timeout=2)
    group_name = f"booth_{user.pk}.order"
    channel_layer = get_channel_layer()
    served_at = timezone.now().isoformat()
    await channel_layer.group_send(
        group_name,
        {
            "type": "admin_order_completed",
            "data": {
                "order_id": order.id,
                "table_num": 1,
                "served_at": served_at
            }
        }
    )
    response = await communicator.receive_json_from(timeout=2)
    assert response["type"] == "ORDER_COMPLETED"
    assert response["data"]["order_id"] == order.id
    assert response["data"]["table_num"] == 1
    assert response["data"]["served_at"] == served_at
    await communicator.disconnect()
import pytest
from channels.testing import WebsocketCommunicator
from channels.routing import URLRouter
from order.routing import websocket_urlpatterns
from django.contrib.auth import get_user_model
from asgiref.sync import sync_to_async
from channels.layers import get_channel_layer
from order.models import Order, OrderItem

User = get_user_model()
 # application은 asgi.py의 application을 import해서 사용

@pytest.mark.asyncio
@pytest.mark.django_db(transaction=True)
async def test_admin_order_websocket_connect(settings):
    settings.CHANNEL_LAYERS = {
        "default": {
            "BACKEND": "channels.layers.InMemoryChannelLayer"
        }
    }
    user = await sync_to_async(User.objects.create_user)(username="admin_test", password="password")
    communicator = WebsocketCommunicator(application, "/ws/django/admin/orders/management/")
    communicator.scope["user"] = user
    connected, _ = await communicator.connect()
    assert connected
    try:
        await communicator.receive_json_from(timeout=2)
    except Exception:
        pass
    await communicator.disconnect()

# 실제 주문 이벤트 메시지 송수신 테스트
@pytest.mark.asyncio
@pytest.mark.django_db(transaction=True)
async def test_admin_order_event_message(settings):
    settings.CHANNEL_LAYERS = {
        "default": {
            "BACKEND": "channels.layers.InMemoryChannelLayer"
        }
    }
    user = await sync_to_async(User.objects.create_user)(username="admin_test2", password="password")
    communicator = WebsocketCommunicator(application, "/ws/django/admin/orders/management/")
    communicator.scope["user"] = user
    connected, _ = await communicator.connect()
    assert connected
    try:
        await communicator.receive_json_from(timeout=2)
    except Exception:
        pass

    # 주문 및 아이템 생성
    order = await sync_to_async(Order.objects.create)(order_price=10000, order_status="PAID")
    await sync_to_async(OrderItem.objects.create)(order=order, menu=1, quantity=1, fixed_price=10000)

    # group_name 생성
    group_name = f"booth_{user.pk}.order"
    channel_layer = get_channel_layer()
    # admin_new_order 이벤트 전송
    await channel_layer.group_send(
        group_name,
        {
            "type": "admin_new_order",
            "order": {"order_id": order.id, "order_status": "PAID"}
        }
    )
    # 메시지 수신 및 검증
    response = await communicator.receive_json_from(timeout=5)
    assert response["type"] == "ADMIN_NEW_ORDER"
    assert response["data"]["order"]["order_id"] == order.id
    assert response["data"]["order"]["order_status"] == "PAID"
    await communicator.disconnect()


import pytest

from channels.testing import WebsocketCommunicator
from channels.routing import URLRouter
from order.routing import websocket_urlpatterns
from django.contrib.auth import get_user_model
from asgiref.sync import sync_to_async

User = get_user_model()
 # application은 asgi.py의 application을 import해서 사용

@pytest.mark.asyncio
@pytest.mark.django_db(transaction=True)
async def test_admin_order_websocket_connect(settings):
    settings.CHANNEL_LAYERS = {
        "default": {
            "BACKEND": "channels.layers.InMemoryChannelLayer"
        }
    }
    user = await sync_to_async(User.objects.create_user)(username="admin_test", password="password")
    communicator = WebsocketCommunicator(application, "/ws/django/admin/orders/management/")
    communicator.scope["user"] = user
    connected, _ = await communicator.connect()
    assert connected
    try:
        await communicator.receive_json_from(timeout=2)
    except Exception:
        pass
    await communicator.disconnect()
