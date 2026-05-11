from rest_framework import serializers


class AddToCartSerializer(serializers.Serializer):
    table_usage_id = serializers.IntegerField()
    type = serializers.ChoiceField(choices=["menu", "fee", "setmenu"])
    menu_id = serializers.IntegerField(required=False, allow_null=True)
    set_menu_id = serializers.IntegerField(required=False, allow_null=True)
    quantity = serializers.IntegerField(min_value=1)

    def validate(self, attrs):
        t = attrs["type"]

        if t in ["menu", "fee"]:
            if not attrs.get("menu_id"):
                raise serializers.ValidationError(
                    {"menu_id": f"type={t}이면 menu_id는 필수입니다."}
                )
            if attrs.get("set_menu_id") is not None:
                raise serializers.ValidationError(
                    {"set_menu_id": f"type={t}이면 set_menu_id는 null이어야 합니다."}
                )

        elif t == "setmenu":
            if not attrs.get("set_menu_id"):
                raise serializers.ValidationError(
                    {"set_menu_id": "type=setmenu이면 set_menu_id는 필수입니다."}
                )
            if attrs.get("menu_id") is not None:
                raise serializers.ValidationError(
                    {"menu_id": "type=setmenu이면 menu_id는 null이어야 합니다."}
                )

        return attrs


class CartDetailQuerySerializer(serializers.Serializer):
    table_usage_id = serializers.IntegerField()


class UpdateQuantitySerializer(serializers.Serializer):
    table_usage_id = serializers.IntegerField()
    cart_item_id = serializers.IntegerField()
    quantity = serializers.IntegerField(min_value=0)


class DeleteItemSerializer(serializers.Serializer):
    table_usage_id = serializers.IntegerField()
    cart_item_id = serializers.IntegerField()


class PaymentInfoSerializer(serializers.Serializer):
    table_usage_id = serializers.IntegerField()
    

class PaymentCancelSerializer(serializers.Serializer):
    table_usage_id = serializers.IntegerField()
    
class PaymentConfirmSerializer(serializers.Serializer):
    table_usage_id = serializers.IntegerField()


class CartResetSerializer(serializers.Serializer):
    table_usage_id = serializers.IntegerField()