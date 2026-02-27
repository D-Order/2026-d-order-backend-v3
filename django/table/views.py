from rest_framework import viewsets, status, views
from rest_framework.decorators import action # Removed since no custom actions are kept
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.response import Response # Removed since no custom actions are kept
from .models import Table
from booth.models import Booth
from .serializers import TableListSerializer
from .services import TableService

class TableManagementViewSet(viewsets.ReadOnlyModelViewSet):

    serializer_class = TableListSerializer
    permission_classes = [IsAuthenticated]
    lookup_field = 'table_num'
    def list(self, request, *args, **kwargs):
        queryset = self.get_queryset()
        serializer = self.get_serializer(queryset, many=True)
        return Response({
            'message': '테이블 목록을 조회했습니다.',
            'data': serializer.data
        }, status=status.HTTP_200_OK)
    
    def retrieve(self, request, *args, **kwargs):
        instance = self.get_queryset().filter(table_num=kwargs.get('table_num')).first()
        serializer = self.get_serializer(instance)
        return Response({
            'message': '테이블 디테일을 조회했습니다.',
            'data': serializer.data
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