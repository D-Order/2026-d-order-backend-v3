from rest_framework import serializers
from django.contrib.auth.models import User
from django.db import transaction

from booth.models import Booth

class BoothSerializer(serializers.ModelSerializer):
    class Meta:
        model = Booth
        # 요청받는 필드들 정의
        fields = [
            'name',
            'table_max_cnt',
            'account',
            'depositor',
            'bank',
            'seat_type',
            'seat_fee_person',
            'seat_fee_table',
            'table_limit_hours'
        ]