import logging

from .models import Table, TableGroup, TableUsage
from django.utils.timezone import now
from django.db import transaction
from rest_framework.exceptions import ValidationError, NotFound
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync
from core.redis_client import publish

logger = logging.getLogger(__name__)


class OrderBroadcastService:
    """주문 변경 시 테이블 WebSocket 그룹으로 브로드캐스트

    - booth_{booth_id}.tables      → 목록 뷰 (최근 3개 주문 요약)
    - booth_{booth_id}.tables.{n}  → 상세 뷰 (전체 주문 목록)
    """

    @staticmethod
    def _build_order_items(order):
        """주문의 부모 레벨 아이템 목록 구성"""
        from order.models import OrderItem

        parent_items = (
            OrderItem.objects
            .filter(order=order, parent__isnull=True)
            .select_related("menu", "setmenu")
            .order_by("id")
        )
        items = []
        for item in parent_items:
            if item.setmenu_id:
                name = item.setmenu.name
                menu_id = item.setmenu_id
                from_set = True
            else:
                name = item.menu.name if item.menu else "알 수 없음"
                menu_id = item.menu_id
                from_set = False

            items.append({
                "id": item.pk,
                "menu_id": menu_id,
                "name": name,
                "quantity": item.quantity,
                "fixed_price": item.fixed_price,
                "item_total_price": item.fixed_price * item.quantity,
                "status": item.status,
                "from_set": from_set,
            })
        return items

    @staticmethod
    def _build_order_summary(order):
        """단일 주문 요약 데이터"""
        from django.utils import timezone as tz

        return {
            "order_id": order.pk,
            "order_status": order.order_status,
            "created_at": tz.localtime(order.created_at).isoformat(),
            "order_fixed_price": order.order_price,
            "order_items": OrderBroadcastService._build_order_items(order),
        }

    @staticmethod
    def broadcast_order_update(booth_id, table_num, table_usage_id):
        """주문 변경사항을 테이블 목록 / 상세 WebSocket 그룹에 전송

        transaction.on_commit() 으로 감싸서 DB 커밋 후에만 전송.
        """

        def _send():
            from order.models import Order

            channel_layer = get_channel_layer()
            if not channel_layer:
                logger.error("[OrderBroadcast] channel_layer 없음")
                return

            try:
                table_usage = TableUsage.objects.get(pk=table_usage_id)
                accumulated_amount = table_usage.accumulated_amount

                # 전체 주문 (CANCELLED 제외)
                orders = (
                    Order.objects
                    .filter(table_usage_id=table_usage_id)
                    .exclude(order_status="CANCELLED")
                    .order_by("created_at")
                )

                original_price = sum(
                    o.original_price or o.order_price for o in orders
                )

                # detail 용: 전체 주문 목록
                all_orders = [
                    OrderBroadcastService._build_order_summary(o)
                    for o in orders
                ]

                # list 용: 최근 3개 (최신순)
                recent_3 = list(orders.order_by("-created_at")[:3])
                recent_3_orders = [
                    OrderBroadcastService._build_order_summary(o)
                    for o in recent_3
                ]

                # ① 목록 그룹
                async_to_sync(channel_layer.group_send)(
                    f"booth_{booth_id}.tables",
                    {
                        "type": "order_update",
                        "data": {
                            "table_num": table_num,
                            "recent_3_orders": recent_3_orders,
                            "accumulated_amount": accumulated_amount,
                        },
                    },
                )

                # ② 상세 그룹
                async_to_sync(channel_layer.group_send)(
                    f"booth_{booth_id}.tables.{table_num}",
                    {
                        "type": "order_update",
                        "data": {
                            "table_num": table_num,
                            "orders": all_orders,
                            "original_price": original_price,
                            "accumulated_amount": accumulated_amount,
                        },
                    },
                )

                logger.info(
                    f"[OrderBroadcast] booth={booth_id} table={table_num} "
                    f"주문 {len(all_orders)}건 브로드캐스트 완료"
                )
            except Exception as e:
                logger.error(f"[OrderBroadcast] 전송 실패: {e}")

        transaction.on_commit(_send)


class TableService:

    @staticmethod
    def _broadcast(booth_pk, event):
        """트랜잭션 커밋 후 WebSocket 그룹에 이벤트를 전송"""
        def send_ws():
            channel_layer = get_channel_layer()
            if channel_layer is None:
                logger.error('[TableService] channel_layer 없어요')
                return
            async_to_sync(channel_layer.group_send)(f'booth_{booth_pk}.tables', event)

        # 이게 있어야 교착 상태에 안 빠져요
        transaction.on_commit(send_ws)

    @staticmethod
    def notify_spring_reset(booth_id, table_nums):
        """테이블 초기화 → Spring에 알림"""
        publish(f"booth:{booth_id}:tables:reset", {
            "table_nums": table_nums,
            "count": len(table_nums)
        })

    # @staticmethod
    # def notify_spring_merge(booth_id, representative_table, table_nums):
    #     """테이블 병합 → Spring에 알림"""
    #     publish(f"booth:{booth_id}:tables:merge", {
    #         "representative_table": representative_table,
    #         "table_nums": table_nums,
    #         "count": len(table_nums)
    #     })

    @staticmethod
    @transaction.atomic
    def init_or_enter_table(booth, table_num):
        """부스 테이블 입장용

        Args:
            booth (Booth Entity): 입장하려는 부스
            table_num (int): 입장하려는 테이블 번호

        Returns:
            table_usage (TableUsage Entity): 테이블 사용 기록 객체

        Raises:
            ValidationError: 입력값이 유효하지 않거나 테이블 상태가 부적절할 때
            NotFound: 테이블을 찾을 수 없을 때
        """
        # 입력 검증
        if not table_num:
            raise ValidationError('테이블 번호는 필수입니다.')

        # 테이블 조회
        table = Table.objects.filter(booth=booth, table_num=table_num).first()
        if not table:
            raise NotFound('해당 테이블을 찾을 수 없습니다.')

        # 상태 검증
        if table.status == Table.Status.INACTIVE:
            raise ValidationError('해당 테이블은 현재 이용할 수 없습니다.')

        # 이미 사용 중인 경우 기존 세션 반환
        if table.status == Table.Status.IN_USE:
            table_usage = TableUsage.objects.filter(table=table, ended_at__isnull=True).first()
            return table_usage

        # 테이블 입장 처리
        table_usage = TableService.create_table_usage(table)
        table.status = Table.Status.IN_USE
        table.save()

        TableService._broadcast(booth.pk, {
            'type': 'enter_table',
            'data': {
                'table_num': table_num,
                'started_at': table_usage.started_at.isoformat(),
            }
        })

        return table_usage

    @staticmethod
    def create_table_usage(table):
        """테이블 사용 기록 생성용 / 세션 겸용

        Args:
            table (Table Entity): 사용 기록을 생성하려는 테이블

        Returns:
            TableUsage Entity: 생성된 테이블 사용 기록 객체
        """
        return TableUsage.objects.create(table=table, started_at=now())

    @staticmethod
    @transaction.atomic
    def reset_tables(booth, table_nums):
        """테이블 초기화 (여러 테이블)

        Args:
            booth (Booth Entity): 부스
            table_nums (list of int): 초기화할 테이블 번호 리스트

        Returns:
            int: 초기화된 테이블 개수

        Raises:
            ValidationError: 입력값이 유효하지 않을 때
            NotFound: 테이블을 찾을 수 없을 때
        """
        # 1. 비어있는 경우
        if not table_nums:
            raise ValidationError('초기화할 테이블 번호를 입력해주세요.')

        # 2. 테이블 조회 (그룹 정보 미리 로드)
        tables = Table.objects.select_related('group').filter(
            booth=booth,
            table_num__in=table_nums,
        )

        if tables.exclude(status=Table.Status.IN_USE).exists():
            raise ValidationError('사용중인 테이블만 초기화 할 수 있습니다.')
        
        # 3. 존재하지 않는 테이블 확인
        found_count = tables.count()
        if found_count != len(table_nums):
            found_nums = set(tables.values_list('table_num', flat=True))
            missing_nums = set(table_nums) - found_nums
            raise NotFound(f'테이블을 찾을 수 없습니다: {sorted(missing_nums)}')



        # 4. 병합된 그룹 해제 및 그룹 삭제
        groups_to_delete = set()
        for table in tables:
            if table.group:
                groups_to_delete.add(table.group.pk)

        if groups_to_delete:
            # 그룹에 속한 모든 테이블로 확장 (병합 테이블 포함)
            tables = Table.objects.filter(
                booth=booth,
                group_id__in=groups_to_delete
            )
            # update 전에 ID 캐싱 (update 후 queryset 재평가 시 group=None으로 결과 0이 됨)
            table_ids = list(tables.values_list('pk', flat=True))
            tables.update(group=None)
            TableGroup.objects.filter(pk__in=groups_to_delete).delete()
            # ID 기준으로 재조회
            tables = Table.objects.filter(pk__in=table_ids)

        found_count = tables.count()

        now_time = now()
        active_usages = TableUsage.objects.filter(
            table__in=tables,
            ended_at__isnull=True
        )

        # XXX : django Lazy Loading 관련
        # 캐시 사용하기
        active_usages_cache = list(active_usages)  # 업데이트 전에 사용 기록을 캐싱

        updated_count = active_usages.update(ended_at=now_time)

        # usage_minutes 계산 (bulk_update 사용)
        if updated_count > 0:
            for usage in active_usages_cache:
                usage.usage_minutes = int(
                    (now_time - usage.started_at).total_seconds() / 60
                )
            TableUsage.objects.bulk_update(active_usages_cache, fields=['usage_minutes'])

        # 6. 테이블 상태 일괄 초기화
        reset_table_nums = list(tables.values_list('table_num', flat=True))
        tables.update(status=Table.Status.ACTIVE)

        TableService._broadcast(booth.pk, {
            'type': 'reset_table',
            'data': {
                'table_nums': reset_table_nums,
                'count': found_count,
            }
        })
        TableService.notify_spring_reset(booth.pk, reset_table_nums)
        return found_count


    @staticmethod
    def _merge_active_usages(all_table_ids, representative_table):
        """병합 대상 테이블들의 활성 TableUsage를 대표 테이블 Usage로 통합

        Order, Cart(CartItem/CartCouponApply), TableCoupon을 대표 usage로 이전한 뒤
        나머지 usage를 삭제한다.

        Args:
            all_table_ids (list of int): 병합 대상 모든 테이블의 PK 목록
            representative_table (Table Entity): 대표 테이블
        """
        from order.models import Order
        from cart.models import Cart
        from coupon.models import TableCoupon

        active_usages = list(
            TableUsage.objects.filter(table_id__in=all_table_ids, ended_at__isnull=True)
        )
        if not active_usages:
            return

        earliest_started_at = min(u.started_at for u in active_usages)
        total_accumulated = sum(u.accumulated_amount for u in active_usages)

        # 대표 usage 결정: 대표 테이블의 활성 usage가 없으면 가장 이른 usage를 재할당
        rep_usage = next((u for u in active_usages if u.table_id == representative_table.id), None)
        if rep_usage is None:
            rep_usage = min(active_usages, key=lambda u: u.started_at)
            rep_usage.table = representative_table
            rep_usage.save(update_fields=['table'])

        other_usage_ids = [u.id for u in active_usages if u.id != rep_usage.id]

        if other_usage_ids:
            # Order: 대표 usage로 일괄 재할당
            Order.objects.filter(table_usage_id__in=other_usage_ids).update(table_usage=rep_usage)

            # Cart: 대표 cart로 병합
            rep_cart = Cart.objects.filter(table_usage=rep_usage).first()
            other_carts = list(
                Cart.objects.prefetch_related('items').filter(table_usage_id__in=other_usage_ids)
            )

            # 대표 cart 없으면 other_carts 중 첫 번째를 재할당
            if rep_cart is None and other_carts:
                rep_cart = other_carts.pop(0)
                rep_cart.table_usage = rep_usage
                rep_cart.save(update_fields=['table_usage'])
                # pop된 cart의 pending 쿠폰 반환
                # (이후 루프에서 other_carts만 처리하므로 여기서 명시적으로 처리)
                rep_cart.applied_coupons.filter(round=rep_cart.round).delete()

            # 나머지 other_carts 아이템을 rep_cart에 병합
            if rep_cart and other_carts:
                for other_cart in other_carts:
                    for item in other_cart.items.all():
                        filter_key = 'menu_id' if item.menu_id else 'setmenu_id'
                        existing = rep_cart.items.filter(**{filter_key: getattr(item, filter_key)}).first()
                        if existing:
                            # 동일 메뉴 존재 → 수량만 합산 (UniqueConstraint 충돌 방지)
                            existing.quantity += item.quantity
                            existing.save(update_fields=['quantity'])
                        else:
                            item.cart = rep_cart
                            item.save(update_fields=['cart'])
                    rep_cart.cart_price += other_cart.cart_price
                rep_cart.save(update_fields=['cart_price'])

                # CartCouponApply: rep_cart으로 히스토리 보존
                # rep_cart.round 기준으로 시작 → pending 쿠폰(현재 라운드)을 건드리지 않음
                # pop된 경우 pending 쿠폰이 이미 삭제됐으므로 현재 round는 빈 슬롯
                round_offset = rep_cart.round
                for other_cart in other_carts:
                    for apply in other_cart.applied_coupons.order_by('round'):
                        if apply.round < other_cart.round:
                            # 과거 라운드 (주문 완료된 기록) → rep_cart로 이전
                            round_offset += 1
                            apply.cart = rep_cart
                            apply.round = round_offset
                            apply.save(update_fields=['cart', 'round'])
                        else:
                            # 현재 라운드 (주문 전 pending 쿠폰) → 삭제하여 코드 반환
                            # CouponCode.used_at은 결제 확정 시에만 설정되므로 별도 초기화 불필요
                            apply.delete()
                # rep_cart.round이 마이그레이션된 round보다 작으면 맞춰줌
                # (다음 cart.round += 1 시 충돌 방지)
                if round_offset > rep_cart.round:
                    rep_cart.round = round_offset
                    rep_cart.save(update_fields=['round'])

            # 나머지 other_usage_ids의 cart 삭제 (CartItem CASCADE, CartCouponApply는 이미 이전됨)
            Cart.objects.filter(table_usage_id__in=other_usage_ids).delete()

            # TableCoupon: 대표에 없으면 하나 재할당, 나머지 삭제
            if not TableCoupon.objects.filter(table_usage=rep_usage).exists():
                other_coupon = TableCoupon.objects.filter(table_usage_id__in=other_usage_ids).first()
                if other_coupon:
                    other_coupon.table_usage = rep_usage
                    other_coupon.save(update_fields=['table_usage'])
            # 재할당된 쿠폰은 table_usage가 변경됐으므로 아래 delete에서 제외됨
            TableCoupon.objects.filter(table_usage_id__in=other_usage_ids).delete()

            # other usage 삭제 (관련 레코드 모두 처리 완료)
            TableUsage.objects.filter(id__in=other_usage_ids).delete()

        # rep_usage 최종 업데이트
        rep_usage.started_at = earliest_started_at
        rep_usage.accumulated_amount = total_accumulated
        rep_usage.save(update_fields=['started_at', 'accumulated_amount'])

    @staticmethod
    @transaction.atomic
    def merge_tables(booth, table_nums):
        """테이블 병합 그룹 생성하고 연결 (관리자 전용)

        요청할때 이미 병합된 테이블은 선택 못 하니깐 개별 테이블이랑 대표 테이블 번호만 요청한다고 가정함.
        대표 테이블은 그룹 내 하위 테이블들 다 set에 저장하고 그룹 푼 담에 다시 다 연결하는 방식임.
        대표는 낮은 번호로 선택하는걸로

        Args:
            booth (Booth Entity): 부스
            table_nums (list of int): 병합할 테이블 번호 리스트

        Returns:
            int: 병합된 테이블 개수 (그룹에 속한 모든 멤버 포함)

        Raises:
            ValidationError: 입력값이 유효하지 않을 때
            NotFound: 테이블을 찾을 수 없을 때
        """
        from django.db.models import Q

        # 1. 최소 개수 검증
        if len(table_nums) < 2:
            raise ValidationError('병합하려면 최소 2개의 테이블이 필요합니다.')

        # 2. 요청된 테이블 조회 - list()로 한 번만 평가 (중복 쿼리 방지)
        requested_tables = list(
            Table.objects.select_related('group').filter(
                booth=booth,
                table_num__in=table_nums
            )
        )

        # 3. 존재하지 않는 테이블 확인 (Python에서 처리, 추가 쿼리 없음)
        if len(requested_tables) != len(table_nums):
            found_nums = {t.table_num for t in requested_tables}
            raise NotFound(f'테이블을 찾을 수 없습니다: {sorted(set(table_nums) - found_nums)}')

        # 4. INACTIVE 테이블 확인 (Python에서 처리, 추가 쿼리 없음)
        if any(t.status == Table.Status.INACTIVE for t in requested_tables):
            raise ValidationError("비활성화 된 테이블은 병합할 수 없어요.")

        # 5. 관련된 모든 그룹 수집 (Python에서 처리, 추가 쿼리 없음)
        groups_to_merge = {t.group_id for t in requested_tables if t.group_id}

        # 6. 병합할 모든 테이블 수집 - list()로 한 번만 평가
        if groups_to_merge:
            all_tables = list(
                Table.objects.filter(
                    booth=booth
                ).filter(
                    Q(group_id__in=groups_to_merge) | Q(table_num__in=table_nums)
                )
            )
        else:
            all_tables = requested_tables

        # 7. Python에서 count, nums, 대표 테이블 한꺼번에 계산 (추가 쿼리 없음)
        all_tables_count = len(all_tables)
        merged_table_nums = [t.table_num for t in all_tables]
        representative_table = min(all_tables, key=lambda t: t.table_num)

        # 8. 활성 TableUsage 통합 (대표 테이블로 병합)
        all_table_ids = [t.id for t in all_tables]
        TableService._merge_active_usages(all_table_ids, representative_table)

        # 9. 새 그룹 생성 후 일괄 업데이트
        table_group = TableGroup.objects.create(representative_table=representative_table)
        Table.objects.filter(booth=booth, table_num__in=merged_table_nums).update(group=table_group)

        # 10. 기존 그룹 삭제
        if groups_to_merge:
            TableGroup.objects.filter(pk__in=groups_to_merge).delete()

        TableService._broadcast(booth.pk, {
            'type': 'merge_table',
            'data': {
                'table_nums': merged_table_nums,
                'representative_table': representative_table.table_num,
                'count': all_tables_count,
            }
        })
        return representative_table.table_num, all_tables_count
