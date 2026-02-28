from decimal import Decimal
from rest_framework import serializers
from booth.models import *
from .models import *


class CouponCreateSerializer(serializers.Serializer):
    booth_id = serializers.IntegerField()
    name = serializers.CharField(max_length=50, allow_blank=False)
    description = serializers.CharField(max_length=255, required=False, allow_null=True, allow_blank=True)
    discount_type = serializers.ChoiceField(choices=["RATE", "AMOUNT"])
    discount_value = serializers.DecimalField(max_digits=10, decimal_places=2)
    quantity = serializers.IntegerField(min_value=1)

    def validate_booth_id(self, value):
        if not Booth.objects.filter(id=value).exists():
            raise serializers.ValidationError("존재하지 않는 booth_id 입니다.")
        return value

    def validate(self, attrs):
        dt = attrs["discount_type"]
        dv: Decimal = attrs["discount_value"]

        if dt == "RATE":
            if not (Decimal("0") < dv < Decimal("1")):
                raise serializers.ValidationError({"discount_value": "RATE는 0보다 크고 1보다 작아야 합니다."})
        else:
            if dv < Decimal("1"):
                raise serializers.ValidationError({"discount_value": "AMOUNT는 1 이상이어야 합니다."})

        return attrs


class CouponApplySerializer(serializers.Serializer):
    table_usage_id = serializers.IntegerField()
    coupon_code = serializers.CharField(max_length=16, allow_blank=False)


class CouponCancelSerializer(serializers.Serializer):
    table_usage_id = serializers.IntegerField()