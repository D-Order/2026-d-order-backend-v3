from rest_framework import serializers

from booth.models import Booth

class BoothSerializer(serializers.ModelSerializer):
    class Meta:
        model = Booth
        # 요청받는 필드들 정의
        fields = [
            'name',
            'table_max_cnt',
            'bank',
            'account',
            'depositor',
            'seat_type',
            'seat_fee_person',
            'seat_fee_table',
            'table_limit_hours'
        ]

class BoothUpdateSerializer(BoothSerializer):
      """
      PATCH 전용 (BoothSerializer 상속)
      - table_max_cnt만 read_only로 오버라이드
      """
      table_max_cnt = serializers.IntegerField(read_only=True) 