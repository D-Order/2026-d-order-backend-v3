import logging
from django.db import models, transaction
from django.utils import timezone
from .models import Order, OrderItem
from table.models import TableUsage
from cart.models import Cart, CartItem

logger = logging.getLogger(__name__)


class OrderService:
    """
    Redis 이벤트 기반 주문 생성/취소 서비스
    - payment.confirmed → Order 생성
    - order.cancelled   → Cart 복구
    - spring ServingTask 취소 → OrderItem ROLLBACK (SERVED → COOKED)
    """

    # ─────────────────────────────────────────────
    # 주문 아이템 상태 변경
    # ─────────────────────────────────────────────
    VALID_STATUSES = {"COOKING", "COOKED", "SERVED"}

    @staticmethod
    @transaction.atomic
    def update_order_item_status(order_item_id: int, target_status: str, booth_id: int) -> dict:
        """
        OrderItem 상태를 변경하고, 필요 시 Redis/WebSocket 이벤트를 발행한다.

        - COOKING → COOKED: cooked_at 기록, Redis 발행 (스프링부트 서빙 로봇 알림)
        - any → SERVED:     served_at 기록
        - 전체 아이템 SERVED 시: Order.order_status → COMPLETED, ORDER_COMPLETED 웹소켓
        """
        target_status = target_status.upper()

        if target_status not in OrderService.VALID_STATUSES:
            return {"error": "invalid_status", "message": f"유효하지 않은 상태입니다: {target_status}"}

        try:
            item = (
                OrderItem.objects
                .select_related("order__table_usage__table", "menu", "setmenu", "parent__setmenu")
                .select_for_update(of=("self",))
                .get(pk=order_item_id)
            )
        except OrderItem.DoesNotExist:
            return {"error": "not_found", "message": "해당 주문 항목을 찾을 수 없습니다."}

        # 세트메뉴 부모 아이템은 직접 상태 변경 불가 (자식 개별 관리)
        if item.setmenu_id and item.parent_id is None:
            return {"error": "invalid_target", "message": "세트메뉴의 개별 구성품에서 상태를 변경해주세요."}

        # 권한 체크: 해당 부스 소유의 주문만 변경 가능
        order = item.order
        item_booth_id = order.table_usage.table.booth_id
        if item_booth_id != booth_id:
            return {"error": "forbidden", "message": "해당 부스의 주문이 아닙니다."}

        # 이미 같은 상태면 무시
        if item.status == target_status:
            return {"error": "same_status", "message": f"이미 {target_status} 상태입니다."}

        now = timezone.now()
        old_status = item.status

        # 상태 변경
        item.status = target_status
        update_fields = ["status"]

        if target_status == "COOKED":
            item.cooked_at = now
            update_fields.append("cooked_at")
        elif target_status == "SERVED":
            item.served_at = now
            update_fields.append("served_at")

        item.save(update_fields=update_fields)

        logger.info(
            f"[OrderItem 상태 변경] item_id={order_item_id} "
            f"{old_status} → {target_status}"
        )

        # 메뉴명 결정 (자식 아이템이면 부모 세트메뉴명 포함)
        if item.parent_id is not None:
            # 세트메뉴 자식 아이템
            menu_name = item.menu.name if item.menu_id else "알 수 없음"
            set_menu_name = item.parent.setmenu.name if item.parent and item.parent.setmenu_id else None
        elif item.menu_id:
            menu_name = item.menu.name
            set_menu_name = None
        else:
            menu_name = "알 수 없음"
            set_menu_name = None

        table_num = order.table_usage.table.table_num

        # ─── COOKING → Redis 발행 (서빙 요청 취소) ───
        # 조리중으로 다시 변경되었을 때 (COOKED → COOKING), Spring의 ServingTask 제거
        if target_status == "COOKING" and old_status == "COOKED":
            try:
                from core.redis_client import publish
                publish(
                    f"booth:{booth_id}:order:cooking",
                    {
                        "event": "SERVING_CANCELLED",
                        "order_item_id": order_item_id,
                        "table_num": table_num,
                        "menu_name": menu_name,
                        "quantity": item.quantity,
                        "reason": "조리 다시 시작",
                        "timestamp": timezone.localtime(now).isoformat(),
                    }
                )
                logger.info(
                    f"[ServingTask 취소] order_item_id={order_item_id}, "
                    f"테이블={table_num}, 메뉴={menu_name}"
                )
            except Exception as e:
                logger.error(f"[OrderItem] Redis 발행 실패 (COOKING): {e}")

        # ─── COOKED → Redis 발행 (스프링부트 서빙 알림) ───
        if target_status == "COOKED":
            try:
                from core.redis_client import publish
                publish(
                    f"booth:{booth_id}:order:cooked",
                    {
                        "order_item_id": order_item_id,
                        "table_num": table_num,
                        "menu_name": menu_name,
                        "quantity": item.quantity,
                        "status": "cooked",
                        "pushed_at": timezone.localtime(now).isoformat(),
                    }
                )
            except Exception as e:
                logger.error(f"[OrderItem] Redis 발행 실패: {e}")

        # ─── SERVED → Redis 발행 (스프링부트 ServingTask 완료) ───
        if target_status == "SERVED":
            try:
                from core.redis_client import publish
                publish(
                    f"booth:{booth_id}:order:served",
                    {
                        "event": "ORDER_ITEM_SERVED",
                        "order_item_id": order_item_id,
                        "table_num": table_num,
                        "menu_name": menu_name,
                        "status": "served",
                        "timestamp": timezone.localtime(now).isoformat(),
                    }
                )
            except Exception as e:
                logger.error(f"[OrderItem] Redis 발행 실패 (SERVED): {e}")

        # ─── WebSocket: ADMIN_ORDER_UPDATE (구성품별 items 배열) ───
        try:
            from channels.layers import get_channel_layer
            from asgiref.sync import async_to_sync

            group_name = f"booth_{booth_id}.order"
            channel_layer = get_channel_layer()

            items_payload = [{
                "order_item_id": order_item_id,
                "menu_name": menu_name,
                "status": target_status,
                "is_set": item.parent_id is not None,
                "set_menu_name": set_menu_name,
                "parent_order_item_id": item.parent_id,
                "cooked_at": timezone.localtime(item.cooked_at).isoformat() if item.cooked_at else None,
                "served_at": timezone.localtime(item.served_at).isoformat() if item.served_at else None,
            }]

            async_to_sync(channel_layer.group_send)(
                group_name,
                {
                    "type": "admin_order_update",
                    "data": {
                        "order_id": order.pk,
                        "items": items_payload,
                    },
                }
            )
            
            # 메뉴 집계 갱신
            async_to_sync(channel_layer.group_send)(
                group_name,
                {
                    "type": "admin_menu_aggregation",
                    "data": {}
                }
            )
        except Exception as e:
            logger.error(f"[OrderItem] WebSocket ADMIN_ORDER_UPDATE 전송 실패: {e}")

        # ─── 전체 SERVED 체크 → ORDER_COMPLETED ───
        # 리프 아이템만 대상: 세트메뉴 부모(parent=None, setmenu≠None) 제외
        # FEE 카테고리 제외 (테이블 이용료는 상태 변경 대상 아님)
        all_served = not (
            order.items
            .exclude(parent__isnull=True, setmenu__isnull=False)
            .exclude(menu__category="FEE")
            .exclude(status="SERVED")
            .exists()
        )

        response_data = {
            "order_item_id": order_item_id,
            "status": target_status,
            "all_items_served": all_served,
        }

        if target_status == "COOKED":
            response_data["cooked_at"] = timezone.localtime(item.cooked_at).isoformat()
        if target_status == "SERVED":
            response_data["served_at"] = timezone.localtime(item.served_at).isoformat()

        if all_served:
            # Order 상태를 COMPLETED로 변경
            order.order_status = "COMPLETED"
            order.save(update_fields=["order_status"])

            # updated_at은 auto_now이므로 refresh 후 사용
            order.refresh_from_db(fields=["updated_at"])
            updated_at_str = timezone.localtime(order.updated_at).isoformat()

            logger.info(f"[Order 완료] order_id={order.pk} 모든 아이템 서빙 완료")

            try:
                from channels.layers import get_channel_layer
                from asgiref.sync import async_to_sync

                group_name = f"booth_{booth_id}.order"
                channel_layer = get_channel_layer()

                async_to_sync(channel_layer.group_send)(
                    group_name,
                    {
                        "type": "admin_order_completed",
                        "data": {
                            "order_id": order.pk,
                            "table_num": table_num,
                            "table_usage_id": order.table_usage_id,
                            "order_status": "COMPLETED",
                            "updated_at": updated_at_str,
                        },
                    }
                )
            except Exception as e:
                logger.error(f"[OrderItem] WebSocket ORDER_COMPLETED 전송 실패: {e}")

        # ─── 테이블 WebSocket 브로드캐스트 ───
        try:
            from table.services import OrderBroadcastService
            OrderBroadcastService.broadcast_order_update(
                booth_id, table_num, order.table_usage_id
            )
        except Exception as e:
            logger.error(f"[OrderItem] 테이블 WS 브로드캐스트 실패: {e}")

        # 상태에 따른 메시지
        status_messages = {
            "COOKING": "조리중 처리되었습니다.",
            "COOKED": "조리완료 처리되었습니다.",
            "SERVED": "서빙완료 처리되었습니다.",
        }

        return {
            "success": True,
            "message": status_messages[target_status],
            "data": response_data,
        }

    # ─────────────────────────────────────────────
    # 개별 주문 아이템 취소 (부분/전체)
    # ─────────────────────────────────────────────
    @staticmethod
    @transaction.atomic
    def cancel_order_item(order_item_id: int, cancel_quantity: int, booth_id: int) -> dict:
        """
        개별 주문 아이템 취소.

        - 일반 메뉴: 해당 아이템 수량 차감, 0이 되면 CANCELLED
        - 세트메뉴 부모: 부모 + 자식 모두 비례 수량 차감
        - 세트메뉴 자식(parent_id 존재): 직접 취소 불가

        환불 금액 = fixed_price × cancel_quantity
        Order.order_price 차감, TableUsage.accumulated_amount 차감
        WebSocket 브로드캐스트: ADMIN_ORDER_CANCELLED + TOTAL_SALES_UPDATE
        """
        # 1) 대상 아이템 조회
        try:
            item = (
                OrderItem.objects
                .select_related("order__table_usage__table", "menu", "setmenu")
                .select_for_update(of=("self",))
                .get(pk=order_item_id)
            )
        except OrderItem.DoesNotExist:
            return {"error": "not_found", "message": "해당 주문 항목을 찾을 수 없습니다."}

        order = item.order

        # 2) 부스 권한 확인
        if order.table_usage.table.booth_id != booth_id:
            return {"error": "forbidden", "message": "해당 부스의 주문이 아닙니다."}

        # 3) 세트메뉴 자식은 직접 취소 불가
        if item.parent_id is not None:
            return {"error": "invalid_target", "message": "세트메뉴는 세트 단위로만 취소할 수 있습니다."}

        # 4) 이미 취소된 아이템
        if item.status == "CANCELLED":
            return {"error": "already_cancelled", "message": "이미 취소된 주문 항목입니다."}

        # 5) 수량 검증
        if cancel_quantity <= 0:
            return {"error": "invalid_quantity", "message": "취소 수량은 1 이상이어야 합니다."}
        if cancel_quantity > item.quantity:
            return {
                "error": "exceed_quantity",
                "message": f"취소 수량({cancel_quantity})이 현재 수량({item.quantity})을 초과합니다.",
            }

        # 6) 환불 금액 계산
        refund_amount = item.fixed_price * cancel_quantity
        old_quantity = item.quantity
        remaining_quantity = old_quantity - cancel_quantity

        # 7) 아이템 수량 업데이트 + 재고 복구
        from menu.models import Menu

        if remaining_quantity == 0:
            item.quantity = 0
            item.status = "CANCELLED"
            item.save(update_fields=["quantity", "status"])
        else:
            item.quantity = remaining_quantity
            item.save(update_fields=["quantity"])

        # 8) 세트메뉴인 경우 자식들도 비례 수량 조정 + 구성품 재고 복구
        if item.setmenu_id:
            children = OrderItem.objects.filter(parent=item).select_for_update()
            for child in children:
                if old_quantity > 0:
                    child_cancel = cancel_quantity * child.quantity // old_quantity
                    child.quantity -= child_cancel
                    if child.quantity <= 0:
                        child.quantity = 0
                        child.status = "CANCELLED"
                        child.save(update_fields=["quantity", "status"])
                    else:
                        child.save(update_fields=["quantity"])
                    # 구성품 Menu 재고 복구
                    if child.menu_id and child_cancel > 0:
                        Menu.objects.filter(pk=child.menu_id).update(
                            stock=models.F('stock') + child_cancel
                        )
        else:
            # 일반 메뉴 재고 복구
            if item.menu_id:
                Menu.objects.filter(pk=item.menu_id).update(
                    stock=models.F('stock') + cancel_quantity
                )

        # 9) Order.order_price 차감
        order.order_price -= refund_amount
        order.save(update_fields=["order_price", "updated_at"])

        # 9-1) 모든 아이템이 CANCELLED면 Order도 CANCELLED
        # FEE 카테고리 제외 (테이블 이용료는 항상 존재함)
        all_cancelled = not (
            order.items
            .exclude(status="CANCELLED")
            .exclude(parent__isnull=True, setmenu__isnull=False)  # 세트메뉴 부모 쉘 제외
            .exclude(menu__category="FEE")  # FEE 제외
            .exists()
        )
        if all_cancelled:
            order.order_status = "CANCELLED"
            order.save(update_fields=["order_status"])
            logger.info(f"[Order 전체 취소] order_id={order.pk} 모든 아이템 취소됨")

        # 10) TableUsage.accumulated_amount 차감
        table_usage = TableUsage.objects.select_for_update().get(pk=order.table_usage_id)
        table_usage.accumulated_amount -= refund_amount
        table_usage.save(update_fields=["accumulated_amount"])

        # 11) 오늘 매출 캐시 감소 (DB 쿼리 대체)
        from order.cache import update_today_revenue
        new_total_sales = update_today_revenue(booth_id, -refund_amount)

        new_item_total_price = item.fixed_price * remaining_quantity

        logger.info(
            f"[OrderItem 취소] item_id={order_item_id} "
            f"qty={old_quantity}→{remaining_quantity} "
            f"환불={refund_amount:,} 새매출={new_total_sales:,}"
        )

        # 12) WebSocket 브로드캐스트
        try:
            from channels.layers import get_channel_layer
            from asgiref.sync import async_to_sync

            group_name = f"booth_{booth_id}.order"
            channel_layer = get_channel_layer()

            # ADMIN_ORDER_CANCELLED
            async_to_sync(channel_layer.group_send)(
                group_name,
                {
                    "type": "admin_order_cancelled",
                    "data": {
                        "order_id": order.pk,
                        "item_id": order_item_id,
                        "refund_amount": refund_amount,
                        "remaining_quantity": remaining_quantity,
                        "new_total_sales": new_total_sales,
                    },
                }
            )

            # 오늘 매출 갱신 이벤트 (계산된 값 포함)
            async_to_sync(channel_layer.group_send)(
                group_name,
                {"type": "total_sales_update", "data": {"today_revenue": new_total_sales}}
            )
        except Exception as e:
            logger.error(f"[OrderItem 취소] WebSocket 전송 실패: {e}")

        # 13) Redis 발행 → 스프링부트 (손님 환불 알림)
        try:
            import uuid
            from core.redis_client import publish

            menu_name = (
                item.setmenu.name if item.setmenu_id
                else (item.menu.name if item.menu_id else "알 수 없음")
            )
            now_str = timezone.localtime().isoformat()

            publish(
                f"booth:{booth_id}:order:refund",
                {
                    "event_id": str(uuid.uuid4()),
                    "event_type": "order.item_refund",
                    "occurred_at": now_str,
                    "data": {
                        "table_usage_id": order.table_usage_id,
                        "order_id": order.pk,
                        "order_item_id": order_item_id,
                        "menu_name": menu_name,
                        "cancel_quantity": cancel_quantity,
                        "refund_price": refund_amount,
                        "is_full_cancel": remaining_quantity == 0,
                        "pushed_at": now_str,
                    },
                }
            )
        except Exception as e:
            logger.error(f"[OrderItem 취소] Redis 환불 알림 발행 실패: {e}")

        # 14) 테이블 WebSocket 브로드캐스트
        try:
            from table.services import OrderBroadcastService
            table_num = order.table_usage.table.table_num
            OrderBroadcastService.broadcast_order_update(
                booth_id, table_num, order.table_usage_id
            )
        except Exception as e:
            logger.error(f"[OrderItem 취소] 테이블 WS 브로드캐스트 실패: {e}")

        return {
            "success": True,
            "message": "주문 항목이 취소되었습니다.",
            "data": {
                "order_item_id": order_item_id,
                "remaining_quantity": remaining_quantity,
                "refund_amount": refund_amount,
                "new_item_total_price": new_item_total_price,
                "new_total_sales": new_total_sales,
            },
        }

    # ─────────────────────────────────────────────
    # Redis 구독: 스프링부트 → 서빙중/서빙완료 이벤트
    # ─────────────────────────────────────────────
    @staticmethod
    @transaction.atomic
    def handle_serving_event(event_data: dict, action: str) -> dict:
        """
        스프링부트에서 발행한 서빙 이벤트를 처리.

        action:
          - "serving": OrderItem.status → SERVING
          - "served":  OrderItem.status → SERVED + served_at 기록
                       전체 아이템 SERVED 시 Order → COMPLETED

        event_data:
          - order_item_id: int
          - status: str ("serving" | "served")
          - catched_by: str (serving 시만)
          - pushed_at: str
        """
        order_item_id = event_data.get("order_item_id")
        if not order_item_id:
            logger.warning(f"[Serving] order_item_id 누락: {event_data}")
            return {"result": "missing_order_item_id"}

        target_status = "SERVING" if action == "serving" else "SERVED"

        try:
            item = (
                OrderItem.objects
                .select_related("order__table_usage__table", "menu", "setmenu", "parent__setmenu")
                .select_for_update(of=("self",))
                .get(pk=order_item_id)
            )
        except OrderItem.DoesNotExist:
            logger.warning(f"[Serving] OrderItem 없음: id={order_item_id}")
            return {"result": "not_found"}

        # 세트메뉴 부모 아이템은 직접 상태 변경 불가
        if item.setmenu_id and item.parent_id is None:
            logger.warning(f"[Serving] 세트메뉴 부모 아이템 상태 변경 시도: id={order_item_id}")
            return {"result": "invalid_target"}

        old_status = item.status
        now = timezone.now()

        # 상태 변경
        item.status = target_status
        update_fields = ["status"]

        if target_status == "SERVED":
            item.served_at = now
            update_fields.append("served_at")

        item.save(update_fields=update_fields)

        order = item.order
        table = order.table_usage.table
        booth_id = table.booth_id
        table_num = table.table_num

        # 메뉴명 (자식 아이템이면 부모 세트메뉴명 포함)
        if item.parent_id is not None:
            menu_name = item.menu.name if item.menu_id else "알 수 없음"
            set_menu_name = item.parent.setmenu.name if item.parent and item.parent.setmenu_id else None
        elif item.menu_id:
            menu_name = item.menu.name
            set_menu_name = None
        else:
            menu_name = "알 수 없음"
            set_menu_name = None

        logger.info(
            f"[Serving] item_id={order_item_id} "
            f"{old_status} → {target_status} (booth:{booth_id})"
        )

        # WebSocket: ADMIN_ORDER_UPDATE (구성품별 items 배열)
        try:
            from channels.layers import get_channel_layer
            from asgiref.sync import async_to_sync

            group_name = f"booth_{booth_id}.order"
            channel_layer = get_channel_layer()

            items_payload = [{
                "order_item_id": order_item_id,
                "menu_name": menu_name,
                "status": target_status,
                "is_set": item.parent_id is not None,
                "set_menu_name": set_menu_name,
                "parent_order_item_id": item.parent_id,
                "served_at": timezone.localtime(item.served_at).isoformat() if item.served_at else None,
            }]

            async_to_sync(channel_layer.group_send)(
                group_name,
                {
                    "type": "admin_order_update",
                    "data": {
                        "order_id": order.pk,
                        "items": items_payload,
                    },
                }
            )
            
            # 메뉴 집계 갱신
            async_to_sync(channel_layer.group_send)(
                group_name,
                {
                    "type": "admin_menu_aggregation",
                    "data": {}
                }
            )
        except Exception as e:
            logger.error(f"[Serving] WebSocket ADMIN_ORDER_UPDATE 전송 실패: {e}")

        # SERVED일 때: 전체 아이템 SERVED 체크 → ORDER_COMPLETED
        # 리프 아이템만 대상: 세트메뉴 부모(parent=None, setmenu≠None) 제외
        # FEE 카테고리 제외 (테이블 이용료는 상태 변경 대상 아님)
        if target_status == "SERVED":
            all_served = not (
                order.items
                .exclude(parent__isnull=True, setmenu__isnull=False)
                .exclude(menu__category="FEE")
                .exclude(status="SERVED")
                .exists()
            )

            if all_served:
                order.order_status = "COMPLETED"
                order.save(update_fields=["order_status"])
                order.refresh_from_db(fields=["updated_at"])
                updated_at_str = timezone.localtime(order.updated_at).isoformat()

                logger.info(f"[Order 완료] order_id={order.pk} 모든 아이템 서빙 완료")

                try:
                    from channels.layers import get_channel_layer
                    from asgiref.sync import async_to_sync

                    group_name = f"booth_{booth_id}.order"
                    channel_layer = get_channel_layer()

                    async_to_sync(channel_layer.group_send)(
                        group_name,
                        {
                            "type": "admin_order_completed",
                            "data": {
                                "order_id": order.pk,
                                "table_num": table_num,
                                "table_usage_id": order.table_usage_id,
                                "order_status": "COMPLETED",
                                "updated_at": updated_at_str,
                            },
                        }
                    )
                except Exception as e:
                    logger.error(f"[Serving] WebSocket ORDER_COMPLETED 전송 실패: {e}")

        # ─── 테이블 WebSocket 브로드캐스트 ───
        try:
            from table.services import OrderBroadcastService
            OrderBroadcastService.broadcast_order_update(
                booth_id, table_num, order.table_usage_id
            )
        except Exception as e:
            logger.error(f"[Serving] 테이블 WS 브로드캐스트 실패: {e}")

        return {"result": "success", "status": target_status}

    @staticmethod
    @transaction.atomic
    def create_order_from_event(event_data: dict) -> dict:
        """
        Spring Boot에서 발행한 order.created 이벤트를 처리하여
        Order / OrderItem을 생성하고 Cart를 종료한다.

        Returns:
            dict: {"result": "created" | "duplicate_event" | "duplicate_cart" | "invalid_status"}
        """
        event_id = event_data.get("event_id")
        data = event_data["data"]

        # ① 상태 검증: status가 "completed"일 때만 처리
        if data.get("status") != "completed":
            logger.warning(f"[Order] status가 completed가 아님: {data.get('status')}")
            return {"result": "invalid_status"}

        # ② 멱등성 검사 - event_id 중복
        if event_id and Order.objects.filter(event_id=event_id).exists():
            logger.info(f"[Order] 중복 event_id 무시: {event_id}")
            return {"result": "duplicate_event"}

        # ③ 멱등성 검사 - cart_id 중복
        cart_id = data["cart_id"]
        if Order.objects.filter(cart_id=cart_id).exists():
            logger.info(f"[Order] 이미 해당 cart로 주문 존재, 무시: cart_id={cart_id}")
            return {"result": "duplicate_cart"}

        # ④ Cart 조회
        cart = Cart.objects.select_for_update().get(pk=cart_id)
        table_usage_id = data["table_usage_id"]

        # ⑤ Order 생성 (쿠폰/할인 정보 포함)
        order = Order.objects.create(
            event_id=event_id,
            table_usage_id=table_usage_id,
            cart=cart,
            order_price=data["total_price"],
            original_price=data.get("original_total_price"),
            total_discount=data.get("total_discount", 0),
            coupon_id=data.get("coupon_id"),
            order_status="PAID",
        )

        # ⑥ OrderItem 생성 - Price Snapshot (CartItem.price_at_cart → OrderItem.fixed_price)
        #    세트메뉴: 부모 OrderItem + 구성품별 자식 OrderItem 생성
        #    + Menu.stock 차감
        from menu.models import Menu, SetMenuItem
        cart_items = CartItem.objects.filter(cart=cart).select_related('menu', 'setmenu')
        for cart_item in cart_items:
            parent_item = OrderItem.objects.create(
                order=order,
                menu=cart_item.menu,
                setmenu=cart_item.setmenu,
                parent=None,
                quantity=cart_item.quantity,
                fixed_price=cart_item.price_at_cart,
                status="COOKING",
            )

            if cart_item.setmenu_id:
                # 세트메뉴 → 구성품별 자식 OrderItem 생성 + 구성품 재고 차감
                components = SetMenuItem.objects.filter(
                    set_menu_id=cart_item.setmenu_id
                ).select_related("menu")
                for comp in components:
                    consume_qty = cart_item.quantity * comp.quantity
                    OrderItem.objects.create(
                        order=order,
                        menu=comp.menu,
                        setmenu=None,
                        parent=parent_item,
                        quantity=consume_qty,
                        fixed_price=0,
                        status="COOKING",
                    )
                    # 구성품 Menu 재고 차감
                    Menu.objects.filter(pk=comp.menu_id).update(
                        stock=models.F('stock') - consume_qty
                    )
            else:
                # 일반 메뉴 재고 차감
                if cart_item.menu_id:
                    Menu.objects.filter(pk=cart_item.menu_id).update(
                        stock=models.F('stock') - cart_item.quantity
                    )

        # ⑦ Cart 상태 종료
        cart.status = Cart.Status.ORDERED
        cart.save(update_fields=["status"])

        # ⑧ TableUsage 누적 금액 갱신
        table_usage = TableUsage.objects.select_for_update().get(pk=table_usage_id)
        table_usage.accumulated_amount += order.order_price
        table_usage.save(update_fields=["accumulated_amount"])

        logger.info(
            f"[Order 생성 완료] order_id={order.pk}, cart_id={cart_id}, "
            f"price={order.order_price}, discount={order.total_discount}"
        )

        # ⑨ WebSocket 브로드캐스트
        booth_id = table_usage.table.booth_id
        try:
            from channels.layers import get_channel_layer
            from asgiref.sync import async_to_sync
            from order.cache import update_today_revenue

            # order.order_price를 int로 변환 (Decimal → int)
            order_price_int = int(order.order_price)
            today_revenue = update_today_revenue(booth_id, order_price_int)
            group_name = f"booth_{booth_id}.order"
            channel_layer = get_channel_layer()

            # 트랜잭션 커밋 이후 전송해야 consumer 조회 시 최신 데이터가 보장됨
            def _send_ws_events_after_commit():
                try:
                    async_to_sync(channel_layer.group_send)(
                        group_name,
                        {
                            "type": "admin_new_order",
                            "data": {
                                "order_id": order.pk,
                                "cart_id": cart_id,
                                "table_usage_id": table_usage_id,
                                "order_price": order_price_int,
                                "original_price": int(order.original_price) if order.original_price else 0,
                                "total_discount": int(order.total_discount) if order.total_discount else 0,
                                "order_status": order.order_status,
                            }
                        }
                    )
                    # 오늘 매출 갱신 이벤트 (계산된 값 포함 → Consumer DB 쿼리 불필요)
                    async_to_sync(channel_layer.group_send)(
                        group_name,
                        {"type": "total_sales_update", "data": {"today_revenue": today_revenue}}
                    )
                    # 메뉴 집계 갱신
                    async_to_sync(channel_layer.group_send)(
                        group_name,
                        {"type": "admin_menu_aggregation", "data": {}}
                    )
                except Exception as ws_err:
                    logger.error(f"[Order] WebSocket 전송 실패 (주문은 정상 생성됨): {ws_err}")

            transaction.on_commit(_send_ws_events_after_commit)
        except Exception as ws_err:
            logger.error(f"[Order] WebSocket 준비 실패 (주문은 정상 생성됨): {ws_err}")

        # ⑩ 테이블 WebSocket 브로드캐스트
        try:
            from table.services import OrderBroadcastService
            table_num = table_usage.table.table_num
            OrderBroadcastService.broadcast_order_update(
                booth_id, table_num, table_usage_id
            )
        except Exception as e:
            logger.error(f"[Order] 테이블 WS 브로드캐스트 실패 (주문은 정상 생성됨): {e}")

        # ✅ 주문 생성 성공 반환
        return {"result": "success", "order_id": order.pk}

    # ─────────────────────────────────────────────
    # 결제요청 거절 → Cart 복구 (order.cancelled)
    # 운영자가 결제 확인 슬라이드 전 취소 버튼 클릭
    # StaffCall.status = rejected → Redis Publish → Django 수신
    # ※ Order 생성은 절대 하지 않음. Cart 상태만 복구.
    # ─────────────────────────────────────────────
    @staticmethod
    @transaction.atomic
    def handle_payment_rejected_event(event_data: dict) -> dict:
        """
        Spring Boot에서 발행한 order.cancelled 이벤트를 처리.
        결제 요청이 거절되어, 아직 생성되지 않은 주문 대신
        Cart.status를 pending_payment → active로 복구한다.

        비즈니스 흐름:
          사용자 결제요청 → Cart.status=pending_payment
          → 운영자 거절 → Spring이 order.cancelled 발행
          → Django 수신 → Cart.status=active 복구

        Returns:
            dict: {"result": "success" | "order_already_exists" |
                            "cart_not_found" | "not_pending"}
        """
        data = event_data["data"]
        cart_id = data["cart_id"]
        staff_call_id = data.get("staff_call_id")

        # ① Order 존재 여부 확인
        #    이미 Order가 생성되었으면 절대 롤백하지 않음 (무시)
        if Order.objects.filter(cart_id=cart_id).exists():
            logger.info(f"[PaymentRejected] 이미 Order 존재, 무시: cart_id={cart_id}")
            return {"result": "order_already_exists"}

        # ② Cart 조회
        try:
            cart = Cart.objects.select_for_update().get(pk=cart_id)
        except Cart.DoesNotExist:
            logger.warning(f"[PaymentRejected] Cart 없음: cart_id={cart_id}")
            return {"result": "cart_not_found"}

        # ③ Cart 상태 복구: pending_payment → active
        if cart.status != Cart.Status.PENDING:
            logger.info(
                f"[PaymentRejected] Cart가 pending_payment 상태가 아님: "
                f"cart_id={cart_id}, status={cart.status}"
            )
            return {"result": "not_pending"}

        cart.status = Cart.Status.ACTIVE
        cart.save(update_fields=["status"])

        logger.info(
            f"[PaymentRejected 완료] cart_id={cart_id} → active 복구, "
            f"staff_call_id={staff_call_id}"
        )

        # ④ WebSocket 알림 (사용자 화면에 장바구니 상태로 돌아가도록)
        try:
            from channels.layers import get_channel_layer
            from asgiref.sync import async_to_sync

            table_usage_id = data.get("table_usage_id")
            if table_usage_id:
                table_usage = TableUsage.objects.get(pk=table_usage_id)
                booth_id = table_usage.table.booth_id
                group_name = f"booth_{booth_id}.order"
                async_to_sync(get_channel_layer().group_send)(
                    group_name,
                    {
                        "type": "admin_order_cancelled",
                        "data": {
                            "cart_id": cart_id,
                            "table_usage_id": table_usage_id,
                            "staff_call_id": staff_call_id,
                        }
                    }
                )
        except Exception as ws_err:
            logger.error(f"[PaymentRejected] WebSocket 전송 실패 (Cart 복구는 완료): {ws_err}")

        return {"result": "success"}


    # ─────────────────────────────────────────────
    # 테이블 초기화 시 서빙 태스크 취소
    # ─────────────────────────────────────────────

    @staticmethod
    def cancel_serving_tasks_for_reset(table_usage_ids: list, booth_id: int) -> None:
        """
        테이블 초기화 시 COOKED/SERVING 상태인 OrderItem에 대해
        Spring에 SERVING_CANCELLED Redis 이벤트를 발행한다.

        table_usage_ids: 초기화된 TableUsage ID 목록
        booth_id: 부스 ID
        """
        if not table_usage_ids:
            return

        cooked_items = (
            OrderItem.objects
            .filter(
                order__table_usage_id__in=table_usage_ids,
                status__in=["COOKED", "cooked", "SERVING", "serving"],
            )
            .select_related("menu", "setmenu", "parent__setmenu")
        )

        try:
            from core.redis_client import publish
        except Exception as e:
            logger.error(f"[TableReset] Redis import 실패: {e}")
            return

        now_str = timezone.localtime().isoformat()
        for item in cooked_items:
            if item.parent_id is not None:
                menu_name = item.menu.name if item.menu_id else "알 수 없음"
            elif item.menu_id:
                menu_name = item.menu.name
            else:
                menu_name = item.setmenu.name if item.setmenu_id else "알 수 없음"

            try:
                publish(
                    f"booth:{booth_id}:order:reset",
                    {
                        "event": "SERVING_CANCELLED",
                        "order_item_id": item.pk,
                        "menu_name": menu_name,
                        "quantity": item.quantity,
                        "reason": "테이블 초기화",
                        "timestamp": now_str,
                    }
                )
                logger.info(
                    f"[TableReset] SERVING_CANCELLED 발행: item_id={item.pk}, menu={menu_name}"
                )
            except Exception as e:
                logger.error(f"[TableReset] Redis 발행 실패 item_id={item.pk}: {e}")

    # ─────────────────────────────────────────────
    # 주문 내역 dict 조립
    # ─────────────────────────────────────────────

    @staticmethod
    def build_order_history_data(table_usage, order_limit: int = None) -> dict:
        """
        TableUsage에 대한 주문 내역 dict 반환.
        TableOrderHistoryAPIView(사용자용), 어드민 테이블 목록/상세 등에서 재사용.

        Args:
            table_usage: TableUsage 인스턴스
            order_limit: order_list 반환 개수 제한 (None이면 전체).
                         가격 합산(총액/할인)은 항상 전체 기준으로 계산됨.

        Returns:
            {
                table_usage_id, table_number,
                table_total_price, total_original_price, total_discount_price,
                order_list: [ { order_id, order_status, created_at,
                                has_coupon, coupon_name, table_coupon_id,
                                order_discount_price, order_fixed_price,
                                order_items: [...] } ]
            }
        """
        table = table_usage.table

        orders = (
            Order.objects
            .filter(table_usage=table_usage)
            .exclude(order_status="CANCELLED")
            .order_by("created_at")
        )

        table_coupon = None
        coupon_name = None
        try:
            from coupon.models import TableCoupon
            tc = TableCoupon.objects.select_related("coupon").filter(
                table_usage=table_usage
            ).first()
            if tc:
                table_coupon = tc
                coupon_name = tc.coupon.name
        except Exception:
            pass

        table_total_price = 0
        total_original_price = 0
        total_discount_price = 0
        order_list = []

        for order in orders:
            order_original = order.original_price or order.order_price
            order_discount = order.total_discount or 0
            order_fixed = order.order_price

            table_total_price += order_fixed
            total_original_price += order_original
            total_discount_price += order_discount

            has_coupon = order.coupon_id is not None

            parent_items = (
                OrderItem.objects
                .filter(order=order, parent__isnull=True)
                .select_related("menu", "setmenu")
                .order_by("id")
            )

            order_items = []
            for item in parent_items:
                if item.setmenu_id:
                    name = item.setmenu.name
                    image = item.setmenu.image.url if item.setmenu.image else None
                    menu_id = item.setmenu_id
                    from_set = True
                else:
                    name = item.menu.name if item.menu else "알 수 없음"
                    image = item.menu.image.url if item.menu and item.menu.image else None
                    menu_id = item.menu_id
                    from_set = False

                order_items.append({
                    "id": item.pk,
                    "menu_id": menu_id,
                    "name": name,
                    "image": image,
                    "quantity": item.quantity,
                    "fixed_price": item.fixed_price,
                    "item_total_price": item.fixed_price * item.quantity,
                    "status": item.status,
                    "from_set": from_set,
                })

            order_list.append({
                "order_id": order.pk,
                "order_number": len(order_list) + 1,
                "order_status": order.order_status,
                "created_at": timezone.localtime(order.created_at).isoformat(),
                "has_coupon": has_coupon,
                "coupon_name": coupon_name if has_coupon else None,
                "table_coupon_id": table_coupon.pk if (has_coupon and table_coupon) else None,
                "order_discount_price": order_discount,
                "order_fixed_price": order_fixed,
                "order_items": order_items,
            })

        return {
            "table_usage_id": table_usage.pk,
            "table_number": str(table.table_num),
            "table_total_price": table_total_price,
            "total_original_price": total_original_price,
            "total_discount_price": total_discount_price,
            "order_list": order_list[-order_limit:] if order_limit else order_list,
        }

    # ─────────────────────────────────────────────
    # 서빙 취소 처리 (Spring → Django)
    # spring:booth:{booth_id}:order:cooked 채널 구독
    # ─────────────────────────────────────────────
    @staticmethod
    @transaction.atomic
    def handle_serving_cancelled(event_data: dict) -> dict:
        """
        Spring에서 발행한 서빙 취소 이벤트를 처리.
        서빙 중(SERVED) → 조리 완료(COOKED) 롤백

        event_data:
          - order_item_id: int (필수)
          - booth_id: int (필수)
          - reason: str (optional - 취소 사유)
          - pushed_at: str (optional)

        Returns:
            dict: {"result": "success" | "not_found" | "invalid_status" | ...}
        """
        order_item_id = event_data.get("order_item_id")
        booth_id = event_data.get("booth_id")

        if not order_item_id or not booth_id:
            logger.warning(f"[ServingCancelled] 필수 필드 누락: {event_data}")
            return {"result": "missing_fields"}

        try:
            item = (
                OrderItem.objects
                .select_related("order__table_usage__table", "menu", "setmenu", "parent__setmenu")
                .select_for_update(of=("self",))
                .get(pk=order_item_id)
            )
        except OrderItem.DoesNotExist:
            logger.warning(f"[ServingCancelled] OrderItem 없음: id={order_item_id}")
            return {"result": "not_found"}

        order = item.order
        table = order.table_usage.table

        # 부스 권한 확인
        if table.booth_id != booth_id:
            logger.warning(f"[ServingCancelled] 부스 권한 없음: item_booth={table.booth_id}, target_booth={booth_id}")
            return {"result": "forbidden"}

        # 세트메뉴 부모 아이템은 직접 상태 변경 불가
        if item.setmenu_id and item.parent_id is None:
            logger.warning(f"[ServingCancelled] 세트메뉴 부모 아이템 롤백 시도: id={order_item_id}")
            return {"result": "invalid_target"}

        # SERVING 또는 SERVED 상태에서만 롤백 가능
        if item.status not in ("SERVING", "SERVED"):
            logger.warning(f"[ServingCancelled] 이미 SERVING/SERVED 상태 아님: id={order_item_id}, current_status={item.status}")
            return {"result": "invalid_status"}

        old_status = item.status
        now = timezone.now()
        reason = event_data.get("reason", "Robot error")

        # 상태 변경 (SERVING → COOKED 또는 SERVED → COOKED)
        item.status = "COOKED"
        item.save(update_fields=["status"])

        table_num = table.table_num
        menu_name = (
            item.menu.name if item.menu_id
            else (item.setmenu.name if item.setmenu_id else "알 수 없음")
        )

        logger.info(
            f"[ServingCancelled] item_id={order_item_id} "
            f"{old_status} → COOKED (reason: {reason}, booth: {booth_id})"
        )

        # WebSocket: ADMIN_ORDER_UPDATE
        try:
            from channels.layers import get_channel_layer
            from asgiref.sync import async_to_sync

            group_name = f"booth_{booth_id}.order"
            channel_layer = get_channel_layer()

            if item.parent_id is not None:
                # 세트메뉴 자식 아이템
                set_menu_name = item.parent.setmenu.name if item.parent and item.parent.setmenu_id else None
            else:
                set_menu_name = None

            items_payload = [{
                "order_item_id": order_item_id,
                "menu_name": menu_name,
                "status": "COOKED",
                "is_set": item.parent_id is not None,
                "set_menu_name": set_menu_name,
                "parent_order_item_id": item.parent_id,
                "served_at": timezone.localtime(item.served_at).isoformat() if item.served_at else None,
                "rollback_reason": reason,
            }]

            async_to_sync(channel_layer.group_send)(
                group_name,
                {
                    "type": "admin_order_update",
                    "data": {
                        "order_id": order.pk,
                        "items": items_payload,
                    },
                }
            )
            
            # 메뉴 집계 갱신
            async_to_sync(channel_layer.group_send)(
                group_name,
                {
                    "type": "admin_menu_aggregation",
                    "data": {}
                }
            )
        except Exception as e:
            logger.error(f"[ServingCancelled] WebSocket 전송 실패: {e}")

        # 테이블 WebSocket 브로드캐스트
        try:
            from table.services import OrderBroadcastService
            OrderBroadcastService.broadcast_order_update(
                booth_id, table_num, order.table_usage_id
            )
        except Exception as e:
            logger.error(f"[ServingCancelled] 테이블 WS 브로드캐스트 실패: {e}")

        return {
            "result": "success",
            "order_item_id": order_item_id,
            "old_status": old_status,
            "new_status": "COOKED",
            "reason": reason,
        }
