import logging

from booth.models import Booth
from menu.models import Menu
from table.models import Table, TableGroup, TableUsage
from django.db import transaction
from rest_framework.exceptions import ValidationError

logger = logging.getLogger(__name__)


class BoothService:

    @staticmethod
    def create_booth_for_user(user, booth_data):
        """유저 생성 시 부스 데이터 만드는 함수
        Args:
            user (User): 유저 객체
            booth_data (dict): 부스 데이터
        Returns:
            생성한 Booth 객체
        """
        from table.models import Table

        logger.debug(
            "[BoothService.create_booth_for_user] Booth 생성 시도 | user_id=%s | name=%s | seat_type=%s | table_max_cnt=%s",
            user.id, booth_data.get('name'), booth_data.get('seat_type'), booth_data.get('table_max_cnt')
        )

        # Booth 객체 생성
        booth = Booth.objects.create(
            user=user,
            name=booth_data['name'],
            account=booth_data['account'],
            depositor=booth_data['depositor'],
            bank=booth_data['bank'],
            table_max_cnt=booth_data['table_max_cnt'],
            table_limit_hours=booth_data['table_limit_hours'],
            seat_type=booth_data['seat_type'],
            seat_fee_person=booth_data.get('seat_fee_person'),
            seat_fee_table=booth_data.get('seat_fee_table'),
        )
        logger.debug("[BoothService.create_booth_for_user] Booth 생성 완료 | booth_id=%s", booth.pk)

        # 테이블 이용료 메뉴 자동 생성
        if booth.seat_type == "PP":
            Menu.objects.create(
                booth=booth,
                name="테이블 이용료",
                category="FEE",
                description="인원 수",
                price=booth.seat_fee_person or 0,
                stock=9999
            )
            logger.debug("[BoothService.create_booth_for_user] FEE 메뉴 생성 (PP) | booth_id=%s | price=%s", booth.pk, booth.seat_fee_person)
        elif booth.seat_type == "PT":
            Menu.objects.create(
                booth=booth,
                name="테이블 이용료",
                category="FEE",
                description="테이블",
                price=booth.seat_fee_table or 0,
                stock=9999
            )
            logger.debug("[BoothService.create_booth_for_user] FEE 메뉴 생성 (PT) | booth_id=%s | price=%s", booth.pk, booth.seat_fee_table)
        else:
            Menu.objects.create(
                booth=booth,
                name="테이블 이용료",
                category="FEE",
                description="FREE",
                price=0,
                stock=9999
            )
            logger.debug("[BoothService.create_booth_for_user] FEE 메뉴 생성 (FREE) | booth_id=%s", booth.pk)

        # 테이블 생성
        logger.debug(
            "[BoothService.create_booth_for_user] 테이블 %s개 생성 시작 | booth_id=%s",
            booth.table_max_cnt, booth.pk
        )
        for i in range(1, booth.table_max_cnt + 1):
            Table.objects.create(
                booth=booth,
                table_num=i
            )
        logger.info(
            "[BoothService.create_booth_for_user] 완료 | booth_id=%s | tables=%s | seat_type=%s",
            booth.pk, booth.table_max_cnt, booth.seat_type
        )
        return booth

    @staticmethod
    def update_booth(booth, booth_data):
        """부스 마이페이지 데이터 업데이트 및 FEE 메뉴 동기화
        Args:
            booth_data (dict): 변경할 부스 데이터
        """
        # 기존 값 변경
        for key, value in booth_data.items():
            setattr(booth, key, value)
        booth.save()

        # FEE 메뉴 동기화
        fee_menu = Menu.objects.filter(booth=booth, category="FEE").first()
        if fee_menu:
            if booth.seat_type == "PP":
                fee_menu.price = booth.seat_fee_person or 0
                fee_menu.description = "인원 수"
            elif booth.seat_type == "PT":
                fee_menu.price = booth.seat_fee_table or 0
                fee_menu.description = "테이블"
            else:
                fee_menu.price = 0
                fee_menu.description = "FREE"
            fee_menu.save()

    @staticmethod
    @transaction.atomic
    def reset_booth_table_usage(booth):
        """부스의 모든 TableUsage 삭제 및 테이블 초기화
        Args:
            booth (Booth): 초기화할 부스

        Returns:
            int: 삭제된 TableUsage 개수

        Raises:
            ValidationError: IN_USE 상태의 테이블이 하나라도 있을 때
        """
        # 1. IN_USE 테이블 존재 여부 확인
        if Table.objects.filter(booth=booth, status=Table.Status.IN_USE).exists():
            raise ValidationError('사용 중인 테이블이 있어 초기화할 수 없습니다.')

        # 2. 모든 그룹 해제 및 삭제
        group_ids = list(
            TableGroup.objects
            .filter(tables__booth=booth)
            .values_list('pk', flat=True)
            .distinct()
        )
        if group_ids:
            Table.objects.filter(booth=booth).update(group=None)
            TableGroup.objects.filter(pk__in=group_ids).delete()

        # 3. Order 먼저 삭제 (Order.cart가 PROTECT이므로 Cart 삭제 전에 제거 필요)
        #    Order 삭제 시 OrderItem은 CASCADE로 자동 삭제됨
        from order.models import Order
        Order.objects.filter(table_usage__table__booth=booth).delete()

        from order.cache import invalidate_today_revenue
        invalidate_today_revenue(booth.pk)

        # 4. 모든 TableUsage 삭제
        #    Cart.table_usage가 CASCADE이므로 Cart도 함께 삭제됨
        deleted_count, _ = TableUsage.objects.filter(table__booth=booth).delete()

        # 5. 총매출 0 초기화 WebSocket 전송 (트랜잭션 커밋 후)
        def _send_ws_after_commit():
            try:
                from channels.layers import get_channel_layer
                from asgiref.sync import async_to_sync
                channel_layer = get_channel_layer()
                group_name = f"booth_{booth.pk}.order"
                async_to_sync(channel_layer.group_send)(
                    group_name,
                    {"type": "total_sales_update", "data": {"today_revenue": 0}}
                )
            except Exception as e:
                import logging
                logging.getLogger(__name__).error(f"[부스 초기화] 총매출 WebSocket 전송 실패: {e}")

        transaction.on_commit(_send_ws_after_commit)

        return deleted_count
