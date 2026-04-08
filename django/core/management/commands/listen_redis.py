import json
import re
import logging
from django.core.management.base import BaseCommand
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync
from core.redis_client import psubscribe

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Spring에서 오는 Redis 메시지를 패턴 구독하여 처리'

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS("Spring 메시지 리스너 시작 (패턴 구독)..."))

        channel_layer = get_channel_layer()

        # 패턴 구독: Spring에서 오는 메시지만 수신 (spring: 접두사)
        pubsub = psubscribe([
            "spring:booth:*:order:*",        # 주문 이벤트
            "spring:booth:*:staffcall:*",    # 호출 이벤트
            "spring:booth:*:tables:*",       # 테이블 이벤트
        ])

        self.stdout.write(self.style.SUCCESS("구독 채널 패턴:"))
        self.stdout.write("  - spring:booth:*:order:*")
        self.stdout.write("  - spring:booth:*:staffcall:*")
        self.stdout.write("  - spring:booth:*:tables:*")
        self.stdout.write("")

        for message in pubsub.listen():
            if message["type"] != "pmessage":
                continue

            try:
                channel = message["channel"]
                data = json.loads(message["data"])

                # 채널명 파싱: spring:booth:{id}:{domain}:{action}
                match = re.match(r"spring:booth:(\d+):(\w+):(\w+)", channel)
                if not match:
                    self.stderr.write(self.style.ERROR(f"잘못된 채널 형식: {channel}"))
                    continue

                booth_id, domain, action = match.groups()

                # ──── Order 도메인 처리 ────
                if domain == "order":
                    self._handle_order_event(booth_id, action, data, channel_layer)

                # ──── StaffCall 도메인 처리 ────
                elif domain == "staffcall":
                    self._handle_staffcall_event(booth_id, action, data, channel_layer)

                # ──── 기타 도메인 → WebSocket 브로드캐스트 ────
                else:
                    group_name = f"booth_{booth_id}.{domain}"
                    event_type = f"{action}"
                    async_to_sync(channel_layer.group_send)(
                        group_name,
                        {"type": event_type, "data": data}
                    )

                self.stdout.write(self.style.SUCCESS(f"[{channel}] 처리 완료"))
                self.stdout.write(f"  데이터: {json.dumps(data, ensure_ascii=False)[:200]}")

            except json.JSONDecodeError as e:
                self.stderr.write(self.style.ERROR(f"JSON 파싱 실패: {e}"))
            except Exception as e:
                self.stderr.write(self.style.ERROR(f"메시지 처리 실패: {e}"))
                import traceback
                self.stderr.write(traceback.format_exc())

    def _handle_staffcall_event(self, booth_id, action, data, channel_layer):
        """StaffCall 도메인 이벤트 분기 처리"""

        # 결제확인 완료: spring:booth:{id}:staffcall:completed
        if action == "completed":
            table_usage_id = data.get("table_usage_id")
            call_type = data.get("call_type")

            if call_type == "PAYMENT_CONFIRM" and table_usage_id:
                try:
                    from cart.services import confirm_payment_and_mark_ordered
                    cart = confirm_payment_and_mark_ordered(table_usage_id=table_usage_id)
                    self.stdout.write(self.style.SUCCESS(
                        f"[결제확인] booth:{booth_id} table_usage:{table_usage_id} → Cart#{cart.id} ORDERED"
                    ))
                except Exception as e:
                    self.stderr.write(self.style.ERROR(
                        f"[결제확인 실패] booth:{booth_id} table_usage:{table_usage_id} → {e}"
                    ))
                    import traceback
                    self.stderr.write(traceback.format_exc())

        # 모든 staffcall 이벤트 → WebSocket 브로드캐스트
        group_name = f"booth_{booth_id}.staffcall"
        async_to_sync(channel_layer.group_send)(
            group_name,
            {"type": action, "data": data}
        )

    def _handle_order_event(self, booth_id, action, data, channel_layer):
        """Order 도메인 이벤트 분기 처리"""
        from order.services import OrderService

        # 주문 생성: spring:booth:{id}:order:new
        if action == "new":
            try:
                result = OrderService.create_order_from_event(data)
                self.stdout.write(self.style.SUCCESS(
                    f"[Order 생성] booth:{booth_id} → {result}"
                ))
            except Exception as e:
                self.stderr.write(self.style.ERROR(f"[Order 생성 실패] {e}"))
                import traceback
                self.stderr.write(traceback.format_exc())

        # 결제요청 거절 (Cart 복구): spring:booth:{id}:order:cancel
        elif action == "cancel":
            try:
                result = OrderService.handle_payment_rejected_event(data)
                self.stdout.write(self.style.SUCCESS(
                    f"[결제거절] booth:{booth_id} → Cart 복구 결과: {result}"
                ))
            except Exception as e:
                self.stderr.write(self.style.ERROR(f"[Order 취소 실패] {e}"))
                import traceback
                self.stderr.write(traceback.format_exc())

        # 서빙 수락 / 서빙 완료: spring:booth:{id}:order:serving / served
        elif action in ("serving", "served"):
            try:
                result = OrderService.handle_serving_event(data, action)
                self.stdout.write(self.style.SUCCESS(
                    f"[서빙 {action}] booth:{booth_id} → {result}"
                ))
            except Exception as e:
                self.stderr.write(self.style.ERROR(f"[서빙 {action} 실패] {e}"))
                import traceback
                self.stderr.write(traceback.format_exc())

        # 기타 order 이벤트 → WebSocket 브로드캐스트
        else:
            event_type_map = {
                "update": "admin_order_update",
                "completed": "admin_order_completed",
            }
            event_type = event_type_map.get(action, f"order_{action}")
            group_name = f"booth_{booth_id}.order"
            async_to_sync(channel_layer.group_send)(
                group_name,
                {"type": event_type, "data": data}
            )
