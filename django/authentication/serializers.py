from rest_framework import serializers
from django.contrib.auth.models import User
from django.db import transaction

from booth.models import Booth
from booth.serializers import BoothSerializer

class UserBoothSignupSerializer(serializers.ModelSerializer):
    booth_data = BoothSerializer(write_only=True)
    password = serializers.CharField(write_only=True)

    class Meta:
        model = User
        fields = ['username', 'password', 'booth_data']

    @transaction.atomic # 중간에 실패할 경우 DB 적용 안함
    def create(self, validated_data):
        # 1. User 생성
        user = User.objects.create(username=validated_data['username'])
        user.set_password(validated_data['password'])
        user.save()

        # 2. Booth 자동 생성
        booth = Booth.objects.create(
            user=user,
            name=validated_data['booth_data']['name'],
            account=validated_data['booth_data']['account'],
            depositor=validated_data['booth_data']['depositor'],
            bank=validated_data['booth_data']['bank'],            
            table_max_cnt=validated_data['booth_data']['table_max_cnt'],
            table_limit_hours=validated_data['booth_data']['table_limit_hours'],
            seat_type=validated_data['booth_data']['seat_type'],
            seat_fee_person=validated_data['booth_data']['seat_fee_person'],
            seat_fee_table=validated_data['booth_data']['seat_fee_table'],
        )


        # TODO: Menu 모델 확립 후 다시 구현
        # ✅ 테이블 이용료 메뉴 자동 생성
        # if booth.seat_type == "PP":
        #     Menu.objects.create(
        #         booth=booth,
        #         menu_name="테이블 이용료(1인당)",
        #         menu_description="좌석 이용 요금(1인 기준)",
        #         menu_category="seat_fee",
        #         menu_price=booth.seat_fee_person,
        #         menu_amount=999999  # 사실상 무제한
        #     )
        # elif booth.seat_type == "PT":
        #     Menu.objects.create(
        #         booth=booth,
        #         menu_name="테이블 이용료(테이블당)",
        #         menu_description="좌석 이용 요금(테이블 기준)",
        #         menu_category="seat_fee",
        #         menu_price=booth.seat_fee_table,
        #         menu_amount=999999
        #     )

        # TODO: 테이블 모델 작성 후 다시 구현
        # 테이블 자동 생성
        # for i in range(1, booth.table_max_cnt + 1):
        #     Table.objects.create(
        #         booth=booth,
        #         table_num=i,
        #         status="out",
        #     )
        return user


    