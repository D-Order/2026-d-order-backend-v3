from rest_framework import viewsets, status, views
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.response import Response
from rest_framework.pagination import PageNumberPagination
from .models import Table, TableUsage
from booth.models import Booth
from .serializers import TableListSerializer
from .services import TableService


class TablePagination(PageNumberPagination):
    page_size = 15

class TableManagementViewSet(viewsets.ReadOnlyModelViewSet):

    serializer_class = TableListSerializer
    permission_classes = [IsAuthenticated]
    lookup_field = 'table_num'
    def list(self, request, *args, **kwargs):
        queryset = self.get_queryset()

        active_usages = TableUsage.objects.filter(
            table__in=queryset,
            ended_at__isnull=True,
        ).select_related('table')
        usage_map = {u.table_id: u for u in active_usages}

        serializer = TableListSerializer(
            queryset,
            many=True,
            context={**self.get_serializer_context(), 'usage_map': usage_map},
        )
        return Response({
            'message': '테이블 목록을 조회했습니다.',
            'data': serializer.data,
        }, status=status.HTTP_200_OK)

    def retrieve(self, request, *args, **kwargs):
        from order.serializers import AdminTableOrderHistoryResponseSerializer
        from order.services import OrderService

        instance = self.get_queryset().filter(table_num=kwargs.get('table_num')).first()
        if not instance:
            return Response({'message': '테이블을 찾을 수 없습니다.'}, status=status.HTTP_404_NOT_FOUND)

        usage = TableUsage.objects.filter(table=instance, ended_at__isnull=True).first()
        if not usage:
            return Response({'message': '활성 테이블 세션이 없습니다.'}, status=status.HTTP_404_NOT_FOUND)

        response_data = OrderService.build_order_history_data(usage)
        serializer = AdminTableOrderHistoryResponseSerializer(response_data)
        return Response({
            'message': '테이블 디테일을 조회했습니다.',
            'data': serializer.data,
        }, status=status.HTTP_200_OK)

    def get_queryset(self):
        """현재 로그인한 사용자의 부스 테이블만 조회"""
        return Table.objects.filter(booth=self.request.user.booth).order_by('table_num')


    @action(detail=False, methods=['post'])
    def reset(self, request):
        """테이블 리셋 API

        Request Body:
            - table_nums (list of int): 초기화하려는 테이블 번호들의 리스트

        Returns:
            - 200: 초기화 성공
            - 400: 잘못된 요청 (ValidationError)
            - 404: 테이블을 찾을 수 없음 (NotFound)
        """
        table_nums = request.data.get('table_nums', [])
        booth = request.user.booth

        # Service 레이어 호출 (검증 + 비즈니스 로직)
        count = TableService.reset_tables(booth, table_nums)

        return Response({
            'message': '테이블이 초기화되었습니다.',
            'data' : {
                'reset_table_cnt' : count
            }
        }, status=status.HTTP_200_OK)
    
    @action(detail=False, methods=['post'])
    def merge(self, request):
        """테이블 병합 API

        Request Body:
            - table_nums (list of int): 병합하려는 테이블 번호들의 리스트

        Returns:
            - 200: 병합 성공
            - 400: 잘못된 요청 (ValidationError)
            - 404: 테이블을 찾을 수 없음 (NotFound)
        """
        table_nums = request.data.get('table_nums', [])
        booth = request.user.booth

        representive_table_num, count = TableService.merge_tables(booth, table_nums)

        return Response({
            'message': '테이블이 병합되었습니다.',
            'data' : {
                'representive_table_num' : representive_table_num,
                'merge_table_cnt' : count
            }
        }, status=status.HTTP_200_OK)


class TableEnterAPIView(views.APIView):
    """손님용 테이블 입장 API (비인증)"""
    permission_classes = [AllowAny]
    authentication_classes = []
    
    def post(self, request, booth_id):
        """
        테이블 입장 처리

        Request Body:
            - table_num (int): 테이블 번호

        Returns:
            - 200: 입장 성공 (TableUsage 정보)
            - 400: 잘못된 요청 (ValidationError - DRF 자동 처리)
            - 404: 부스/테이블을 찾을 수 없음 (NotFound - DRF 자동 처리)
        """
        # 부스 조회
        try:
            booth = Booth.objects.get(pk=booth_id)
        except Booth.DoesNotExist:
            return Response({
                "message": "해당 부스를 찾을 수 없습니다."
            }, status=status.HTTP_404_NOT_FOUND)

        # 테이블 번호 추출
        table_num = request.data.get('table_num')

        # ValidationError, NotFound 예외는 DRF가 자동으로 적절한 HTTP 응답으로 변환
        table_usage = TableService.init_or_enter_table(booth, table_num)

        
        # 성공 응답
        return Response({
            'message': '테이블 입장에 성공했습니다.',
            'data': {
                'table_usage_id': table_usage.id,
                'table_num': table_usage.table.table_num,
                'started_at': table_usage.started_at,
            }
        }, status=status.HTTP_200_OK)