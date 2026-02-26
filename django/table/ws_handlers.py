from django.utils import timezone


class TableMixin:
    """테이블 관련 웹소켓 이벤트"""

    async def enter_table(self, event):
        """테이블 입장 이벤트

        Args:
            event : enter_table
                table_num : 테이블 번호
                started_at : 테이블 usage started_at
        """
        await self.send_json({
            'type': 'enter_table',
            'timestamp': timezone.now().isoformat(),
            'message': f"테이블 {event['data']['table_num']}",
            'data': event['data']
        })

    async def reset_table(self, event):
        """테이블 초기화 이벤트

        Args:
            event : reset_table
                count : 리셋된 테이블 수
                table_nums : 리셋된 테이블 번호
        """
        await self.send_json({
            'type': 'reset_table',
            'timestamp': timezone.now().isoformat(),
            'message': f'{event["data"]["count"]}개의 테이블이 초기화되었습니다.',
            'data': event['data']
        })

    async def merge_table(self, event):
        """테이블 병합 이벤트

        Args:
            event : merge_table
                count : 리셋된 테이블 수
                representative_table : 대표 테이블 번호
                table_nums : 리셋된 테이블 번호
        """
        await self.send_json({
            'type': 'merge_table',
            'timestamp': timezone.now().isoformat(),
            'message': f'{event["data"]["count"]}개의 테이블이 병합되었습니다. (대표: {event["data"]["representative_table"]}번)',
            'data': event['data']
        })

    async def update(self, event):
        """테이블 업데이트"""
        data = event["data"]

        # TODO : 서비스 분리
        await self.handle_table_update(data)

        # 클라이언트로 전송
        await self.send_json({
            'type': 'table_update',
            'timestamp': timezone.now().isoformat(),
            'message': '테이블이 업데이트 되었습니다.',
            'data': data
        })

    async def order_update(self, event):
        """주문 변경으로 인한 테이블 목록 업데이트 (최근 3개 주문 요약)

        Args:
            event : order_update
                data : 테이블 업데이트 데이터 (order는 최근 3개만 파싱)
        """
        await self.send_json({
            'type': 'order_update',
            'timestamp': timezone.now().isoformat(),
            'message': '테이블 주문이 업데이트 되었습니다.',
            'data': event['data']
        })


class TableDetailMixin:
    """특정 테이블 상세 웹소켓 이벤트"""

    async def order_update(self, event):
        """주문 변경으로 인한 테이블 상세 업데이트

        Args:
            event : order_update
                data :
                    table_num : 테이블 번호
                    orders : 전체 주문 목록
                    original_price : 할인 전 총액
                    accumulated_amount : 할인 후 총액
        """
        await self.send_json({
            'type': 'order_update',
            'timestamp': timezone.now().isoformat(),
            'message': '테이블 상세페이지 주문이 업데이트 되었습니다.',
            'data': event['data']
        })
