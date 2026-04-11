import os
import pytest
from asgiref.sync import sync_to_async
from channels.layers import get_channel_layer
from channels.testing import WebsocketCommunicator
from django.contrib.auth import get_user_model
from django.utils import timezone

from booth.models import Booth
from menu.models import Menu
from order.models import Order, OrderItem
# 테스트에서는 JWT WebSocket middleware를 비활성화한 라우터를 사용
os.environ.setdefault("DJANGO_ENV", "test")

from project.asgi import application
from table.models import Table, TableUsage

User = get_user_model()


async def create_order_with_items(user, order_status="PAID"):
    booth = await sync_to_async(Booth.objects.create)(
        user=user,
        name="테스트부스",
        account="1234567890",
        depositor="홍길동",
        bank="테스트은행",
        table_max_cnt=10,
        table_limit_hours=2,
        seat_type="NO",
    )
    table = await sync_to_async(Table.objects.create)(booth=booth, table_num=1)
    table_usage = await sync_to_async(TableUsage.objects.create)(table=table, started_at=timezone.now())

    menu = await sync_to_async(Menu.objects.create)(
        booth=booth,
        name="테스트메뉴",
        category="MENU",
        price=5000,
        stock=100,
    )

    order = await sync_to_async(Order.objects.create)(
        order_price=10000,
        order_status=order_status,
        table_usage=table_usage,
    )

    item = await sync_to_async(OrderItem.objects.create)(
        order=order,
        menu=menu,
        quantity=2,
        fixed_price=5000,
        status="COOKING",
    )
    return order, item, table_usage


async def receive_until_type(communicator, target_type, max_attempts=5):
    for _ in range(max_attempts):
        payload = await communicator.receive_json_from(timeout=3)
        if payload.get("type") == target_type:
            return payload
    raise AssertionError(f"{target_type} 메시지를 받지 못했습니다.")


@pytest.mark.asyncio
@pytest.mark.django_db(transaction=True)
async def test_admin_order_snapshot_message(settings):
    settings.CHANNEL_LAYERS = {"default": {"BACKEND": "channels.layers.InMemoryChannelLayer"}}

    user = await sync_to_async(User.objects.create_user)(username="admin_test", password="password")
    order, _, _ = await create_order_with_items(user)

    communicator = WebsocketCommunicator(application, "/ws/django/booth/orders/management/")
    communicator.scope["user"] = user

    connected, _ = await communicator.connect()
    assert connected

    response = await receive_until_type(communicator, "ADMIN_ORDER_SNAPSHOT")
    assert "orders" in response["data"]
    assert response["data"]["orders"][0]["order_id"] == order.id
    assert response["data"]["orders"][0]["table_num"] == 1
    assert response["data"]["orders"][0]["order_status"] == "PAID"

    await communicator.disconnect()


@pytest.mark.asyncio
@pytest.mark.django_db(transaction=True)
async def test_admin_new_order_message(settings):
    settings.CHANNEL_LAYERS = {"default": {"BACKEND": "channels.layers.InMemoryChannelLayer"}}

    user = await sync_to_async(User.objects.create_user)(username="admin_test2", password="password")
    order, _, _ = await create_order_with_items(user)

    communicator = WebsocketCommunicator(application, "/ws/django/booth/orders/management/")
    communicator.scope["user"] = user
    connected, _ = await communicator.connect()
    assert connected

    await receive_until_type(communicator, "ADMIN_ORDER_SNAPSHOT")

    channel_layer = get_channel_layer()
    group_name = f"booth_{user.pk}.order"
    await channel_layer.group_send(
        group_name,
        {
            "type": "admin_new_order",
            "data": {"order_id": order.id},
        },
    )

    response = await receive_until_type(communicator, "ADMIN_NEW_ORDER")
    assert isinstance(response["data"]["orders"], list)
    assert response["data"]["orders"][0]["order_id"] == order.id

    await communicator.disconnect()


@pytest.mark.asyncio
@pytest.mark.django_db(transaction=True)
async def test_admin_order_update_message(settings):
    settings.CHANNEL_LAYERS = {"default": {"BACKEND": "channels.layers.InMemoryChannelLayer"}}

    user = await sync_to_async(User.objects.create_user)(username="admin_test3", password="password")
    order, item, _ = await create_order_with_items(user)

    communicator = WebsocketCommunicator(application, "/ws/django/booth/orders/management/")
    communicator.scope["user"] = user
    connected, _ = await communicator.connect()
    assert connected

    await receive_until_type(communicator, "ADMIN_ORDER_SNAPSHOT")

    channel_layer = get_channel_layer()
    group_name = f"booth_{user.pk}.order"
    await channel_layer.group_send(
        group_name,
        {
            "type": "admin_order_update",
            "data": {
                "order_id": order.id,
                "items": [{"id": item.id, "status": "SERVING", "is_all_served": False}],
            },
        },
    )

    response = await receive_until_type(communicator, "ADMIN_ORDER_UPDATE")
    assert response["data"]["order_id"] == order.id
    assert response["data"]["items"][0]["id"] == item.id
    assert response["data"]["items"][0]["status"] == "SERVING"

    await communicator.disconnect()


@pytest.mark.asyncio
@pytest.mark.django_db(transaction=True)
async def test_admin_order_cancelled_message(settings):
    settings.CHANNEL_LAYERS = {"default": {"BACKEND": "channels.layers.InMemoryChannelLayer"}}

    user = await sync_to_async(User.objects.create_user)(username="admin_test4", password="password")
    order, item, _ = await create_order_with_items(user)

    communicator = WebsocketCommunicator(application, "/ws/django/booth/orders/management/")
    communicator.scope["user"] = user
    connected, _ = await communicator.connect()
    assert connected

    await receive_until_type(communicator, "ADMIN_ORDER_SNAPSHOT")

    channel_layer = get_channel_layer()
    group_name = f"booth_{user.pk}.order"
    await channel_layer.group_send(
        group_name,
        {
            "type": "admin_order_cancelled",
            "data": {
                "order_id": order.id,
                "item_id": item.id,
                "refund_amount": 10000,
                "new_total_sales": 90000,
            },
        },
    )

    response = await receive_until_type(communicator, "ADMIN_ORDER_CANCELLED")
    assert response["data"]["order_id"] == order.id
    assert response["data"]["item_id"] == item.id
    assert response["data"]["refund_amount"] == 10000

    await communicator.disconnect()


@pytest.mark.asyncio
@pytest.mark.django_db(transaction=True)
async def test_admin_order_completed_message(settings):
    settings.CHANNEL_LAYERS = {"default": {"BACKEND": "channels.layers.InMemoryChannelLayer"}}

    user = await sync_to_async(User.objects.create_user)(username="admin_test5", password="password")
    order, _, table_usage = await create_order_with_items(user)

    communicator = WebsocketCommunicator(application, "/ws/django/booth/orders/management/")
    communicator.scope["user"] = user
    connected, _ = await communicator.connect()
    assert connected

    await receive_until_type(communicator, "ADMIN_ORDER_SNAPSHOT")

    channel_layer = get_channel_layer()
    group_name = f"booth_{user.pk}.order"
    updated_at = timezone.now().isoformat()
    await channel_layer.group_send(
        group_name,
        {
            "type": "admin_order_completed",
            "data": {
                "order_id": order.id,
                "table_num": 1,
                "table_usage_id": table_usage.id,
                "order_status": "COMPLETED",
                "updated_at": updated_at,
            },
        },
    )

    response = await receive_until_type(communicator, "ORDER_COMPLETED")
    assert response["data"]["order_id"] == order.id
    assert response["data"]["table_num"] == 1
    assert response["data"]["table_usage_id"] == table_usage.id
    assert response["data"]["order_status"] == "COMPLETED"

    await communicator.disconnect()


@pytest.mark.asyncio
@pytest.mark.django_db(transaction=True)
async def test_admin_order_websocket_connect(settings):
    settings.CHANNEL_LAYERS = {"default": {"BACKEND": "channels.layers.InMemoryChannelLayer"}}

    user = await sync_to_async(User.objects.create_user)(username="admin_test6", password="password")
    await sync_to_async(Booth.objects.create)(
        user=user,
        name="연결테스트부스",
        account="1234567890",
        depositor="홍길동",
        bank="테스트은행",
        table_max_cnt=10,
        table_limit_hours=2,
        seat_type="NO",
    )

    communicator = WebsocketCommunicator(application, "/ws/django/booth/orders/management/")
    communicator.scope["user"] = user
    connected, _ = await communicator.connect()
    assert connected

    msg = await communicator.receive_json_from(timeout=3)
    assert msg["type"] in ["ADMIN_ORDER_SNAPSHOT", "MENU_AGGREGATION"]

    await communicator.disconnect()


@pytest.mark.asyncio
@pytest.mark.django_db(transaction=True)
async def test_admin_order_event_message(settings):
    settings.CHANNEL_LAYERS = {"default": {"BACKEND": "channels.layers.InMemoryChannelLayer"}}

    user = await sync_to_async(User.objects.create_user)(username="admin_test7", password="password")
    order, _, _ = await create_order_with_items(user)

    communicator = WebsocketCommunicator(application, "/ws/django/booth/orders/management/")
    communicator.scope["user"] = user
    connected, _ = await communicator.connect()
    assert connected

    await receive_until_type(communicator, "ADMIN_ORDER_SNAPSHOT")

    channel_layer = get_channel_layer()
    group_name = f"booth_{user.pk}.order"
    await channel_layer.group_send(
        group_name,
        {
            "type": "admin_new_order",
            "data": {"order_id": order.id},
        },
    )

    response = await receive_until_type(communicator, "ADMIN_NEW_ORDER")
    assert response["data"]["orders"][0]["order_id"] == order.id
    assert response["data"]["orders"][0]["order_status"] == "PAID"

    await communicator.disconnect()


@pytest.mark.asyncio
@pytest.mark.django_db(transaction=True)
async def test_table_ended_order_should_not_appear(settings):
    """테이블이 초기화되면 해당 주문은 WebSocket 스냅샷에서 안 보여야 함"""
    settings.CHANNEL_LAYERS = {"default": {"BACKEND": "channels.layers.InMemoryChannelLayer"}}

    user = await sync_to_async(User.objects.create_user)(username="admin_test_table_end", password="password")
    order, _, table_usage = await create_order_with_items(user)

    # 1. 테이블이 사용 중일 때 스냅샷 확인
    communicator = WebsocketCommunicator(application, "/ws/django/booth/orders/management/")
    communicator.scope["user"] = user
    connected, _ = await communicator.connect()
    assert connected

    snapshot_response = await receive_until_type(communicator, "ADMIN_ORDER_SNAPSHOT")
    print(f"✅ 스냅샷 1 (테이블 사용 중): {len(snapshot_response['data']['orders'])}개 주문")
    assert len(snapshot_response["data"]["orders"]) == 1
    assert snapshot_response["data"]["orders"][0]["order_id"] == order.id

    await communicator.disconnect()

    # 2. 테이블을 초기화 (ended_at 설정)
    await sync_to_async(lambda: TableUsage.objects.filter(pk=table_usage.id).update(ended_at=timezone.now()))()

    # 3. 다시 연결하면 주문이 안 나타나야 함
    communicator = WebsocketCommunicator(application, "/ws/django/booth/orders/management/")
    communicator.scope["user"] = user
    connected, _ = await communicator.connect()
    assert connected

    snapshot_response2 = await receive_until_type(communicator, "ADMIN_ORDER_SNAPSHOT")
    print(f"✅ 스냅샷 2 (테이블 초기화 후): {len(snapshot_response2['data']['orders'])}개 주문")
    assert len(snapshot_response2["data"]["orders"]) == 0  # 주문이 없어야 함

    await communicator.disconnect()
