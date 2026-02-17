
import logging

from .models import Table, TableGroup, TableUsage
from django.utils.timezone import now
from django.db import transaction
from rest_framework.exceptions import ValidationError, NotFound
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync

class TableService:

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
        # TODO : 웹소켓 연동해서 테이블 상태 실시간 업데이트
        table_usage = TableService.create_table_usage(table)

        table.status = Table.Status.IN_USE
        table.save()

        channel_layer = get_channel_layer()
        async_to_sync(channel_layer.group_send)(
            f'booth_{booth.pk}.tables',
            {
                'type': 'enter_table',
                'table_num': table_num,
            }
        )

        return table_usage

    @staticmethod
    def create_table_usage(table):
        """테이블 사용 기록 생성용 / 세션 겸용

        Args:
            table (Table Entity): 사용 기록을 생성하려는 테이블

        Returns:
            TableUsage Entity: 생성된 테이블 사용 기록 객체
        """
        
        table_usage = TableUsage.objects.create(table=table, started_at=now())
        
        return table_usage

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
        # TODO : 웹소켓 연동해서 테이블 상태 실시간 업데이트해야함

        # 1. 비어있는 경우
        if not table_nums:
            raise ValidationError('초기화할 테이블 번호를 입력해주세요.')

        # 2. 테이블 조회 (그룹 정보 미리 로드)
        tables = Table.objects.select_related('group').filter(
            booth=booth,
            table_num__in=table_nums
        )

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
            # 해당 그룹의 모든 테이블에서 그룹 연결 해제
            Table.objects.filter(group_id__in=groups_to_delete).update(group=None)
            # 그룹 삭제
            TableGroup.objects.filter(pk__in=groups_to_delete).delete()


        
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
            # 업데이트된 usage들을 다시 조회 (ended_at이 이미 설정됨)
            for usage in active_usages_cache:
                usage.usage_minutes = int(
                    (now_time - usage.started_at).total_seconds() / 60
                )
    
            TableUsage.objects.bulk_update(active_usages_cache, fields=['usage_minutes'])


        # 6. 테이블 상태 일괄 초기화
        tables.update(status=Table.Status.ACTIVE)

        return found_count


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

        # 2. 요청된 테이블 조회 (그룹 정보 포함)
        requested_tables = Table.objects.select_related('group').filter(
            booth=booth,
            table_num__in=table_nums
        )

        # 3. 존재하지 않는 테이블 확인
        requested_count = requested_tables.count()
        if requested_count != len(table_nums):
            found_nums = set(requested_tables.values_list('table_num', flat=True))
            missing_nums = set(table_nums) - found_nums
            raise NotFound(f'테이블을 찾을 수 없습니다: {sorted(missing_nums)}')

        # 4. 관련된 모든 그룹 수집
        groups_to_merge = set()
        for table in requested_tables:
            if table.group:
                groups_to_merge.add(table.group.pk)

        # 5. 병합할 모든 테이블 수집 (그룹에 속한 모든 멤버 포함)
        if groups_to_merge:
            # 그룹에 속한 모든 테이블 + 요청된 개별 테이블
            all_tables = Table.objects.filter(
                booth=booth
            ).filter(
                Q(group_id__in=groups_to_merge) | Q(table_num__in=table_nums)
            )
            
        else:
            # 모두 개별 테이블
            all_tables = requested_tables

        # 6. 가장 낮은 번호의 테이블을 대표로 선택
        representative_table = all_tables.order_by('table_num').first()
        
        
        # 9. 새 그룹 생성
        table_group = TableGroup.objects.create(representative_table=representative_table)
        
        # XXX : django Lazy Loading 관련
        # 아래 로직이 실행되면 기존 그룹이 다 해제됨
        # DJango의 Lazy Loading으로 return시에 합치기 전 그룹 정보로 접근하면 갯수가 안 맞게됨
        # 미리 그룹 갯수 받아서 return하는거로 해결~ / 해결이라고 해도 될지 모르겠음
        # TODO : 여기 최적화하기 (병합 로직이 복잡함.)
        all_tables_count = all_tables.count() 

        all_tables.update(group=table_group)
        
        
        # 8. 기존 그룹 삭제
        if groups_to_merge:
            TableGroup.objects.filter(pk__in=groups_to_merge).delete()
        
        return all_tables.count() 