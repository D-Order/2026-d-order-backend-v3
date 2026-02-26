

class TableMixin:
    """테이블 관련 웹소켓 이벤트"""

    async def enter_table(self, event):
        """_summary_

        Args:
            event : enter_table
                table_num : 테이블 번호
                started_at : 테이블 usage started_at

        """
        await self.send_json({
            'type': 'enter_table',
            'message' : f"테이블 {event['table_num']}",
            'data': {
                'table_num': event['table_num'],
                'started_at': event['started_at']
            }
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
            'message': f'{event["count"]}개의 테이블이 초기화되었습니다.',
            'data' : {
                'table_nums': event['table_nums'],
                'count': event['count']
            }            
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
            'message': f'{event["count"]}개의 테이블이 병합되었습니다. (대표: {event["representative_table"]}번)',
            'data' : {
                'count': event['count'],
                'representative_table': event['representative_table'],
                'table_nums': event['table_nums']
            }     
        })