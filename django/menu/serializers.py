from rest_framework import serializers
from .models import Menu, SetMenu, SetMenuItem
from utils.image import CompressedImageField


class MenuSerializer(serializers.ModelSerializer):
    """Menu 직렬화 - 입력/출력 공통"""
    
    # 입력 필드
    name = serializers.CharField(
        max_length=20,
        min_length=1,
        error_messages={
            'blank': '메뉴 이름은 필수 항목입니다.',
            'required': '메뉴 이름은 필수 항목입니다.',
            'max_length': '메뉴 이름은 20자 이하여야 합니다.',
            'min_length': '메뉴 이름은 빈 문자열일 수 없습니다.',
        }
    )
    category = serializers.ChoiceField(
        choices=Menu.Category.choices,
        error_messages={
            'invalid_choice': 'MENU 또는 DRINK 중 하나를 선택해야 합니다.',
            'required': '카테고리는 필수 항목입니다.',
        }
    )
    description = serializers.CharField(
        max_length=30,
        required=False,
        allow_blank=True,
        allow_null=True,
        error_messages={
            'max_length': '설명은 30자 이하여야 합니다.',
        }
    )
    price = serializers.IntegerField(
        min_value=0,
        error_messages={
            'min_value': '가격은 0원 이상이어야 합니다.',
            'invalid': '가격은 숫자여야 합니다.',
            'required': '가격은 필수 항목입니다.',
        }
    )
    stock = serializers.IntegerField(
        min_value=0,
        error_messages={
            'min_value': '재고수량은 0개 이상이어야 합니다.',
            'invalid': '재고는 정수여야 합니다.',
            'required': '재고수량은 필수 항목입니다.',
        }
    )
    image = CompressedImageField(
        required=False,
        allow_null=True,
        error_messages={
            'invalid_image': '유효한 이미지 파일이 아닙니다.',
        }
    )
    
    # 출력 필드
    menu_id = serializers.IntegerField(source='id', read_only=True)
    booth_id = serializers.IntegerField(source='booth.pk', read_only=True)
    is_soldout = serializers.SerializerMethodField()
    
    class Meta:
        model = Menu
        fields = [
            'menu_id', 'booth_id', 'name', 'category', 'description',
            'price', 'stock', 'image', 'is_soldout', 'created_at', 'updated_at'
        ]
        read_only_fields = ['menu_id', 'booth_id', 'is_soldout', 'created_at', 'updated_at']
    
    def get_is_soldout(self, obj):
        """stock이 0 이하이면 품절"""
        return obj.stock <= 0


class MenuUpdateSerializer(serializers.ModelSerializer):
    """Menu 수정 전용 Serializer (이미지 수정 불가, 삭제만 가능)"""
    
    name = serializers.CharField(
        max_length=20,
        min_length=1,
        required=False,
        error_messages={
            'max_length': '메뉴 이름은 20자 이하여야 합니다.',
            'min_length': '메뉴 이름은 빈 문자열일 수 없습니다.',
        }
    )
    category = serializers.ChoiceField(
        choices=Menu.Category.choices,
        required=False,
        error_messages={
            'invalid_choice': 'MENU 또는 DRINK 중 하나만 선택 가능합니다.',
        }
    )
    description = serializers.CharField(
        max_length=30,
        required=False,
        allow_blank=True,
        allow_null=True,
        error_messages={
            'max_length': '설명은 30자 이하여야 합니다.',
        }
    )
    price = serializers.IntegerField(
        min_value=0,
        required=False,
        error_messages={
            'min_value': '수정할 가격은 0원 이상이어야 합니다.',
            'invalid': '가격은 숫자여야 합니다.',
        }
    )
    stock = serializers.IntegerField(
        min_value=0,
        required=False,
        error_messages={
            'min_value': '수정할 재고수량은 0개 이상이어야 합니다.',
            'invalid': '재고는 정수여야 합니다.',
        }
    )
    image_delete = serializers.BooleanField(
        required=False,
        default=False,
        write_only=True,
    )
    
    # 출력 필드
    menu_id = serializers.IntegerField(source='id', read_only=True)
    booth_id = serializers.IntegerField(source='booth.pk', read_only=True)
    is_soldout = serializers.SerializerMethodField()
    
    class Meta:
        model = Menu
        fields = [
            'menu_id', 'booth_id', 'name', 'category', 'description',
            'price', 'stock', 'image', 'image_delete', 'is_soldout', 'created_at', 'updated_at'
        ]
        read_only_fields = ['menu_id', 'booth_id', 'image', 'is_soldout', 'created_at', 'updated_at']
    
    def get_is_soldout(self, obj):
        """stock이 0 이하이면 품절"""
        return obj.stock <= 0
    
    def validate(self, attrs):
        """이미지 필드가 요청에 포함되어 있으면 에러"""
        request = self.context.get('request')
        if request and 'image' in request.data:
            raise serializers.ValidationError({
                'image': '이미지는 수정할 수 없습니다. image_delete로 삭제만 가능합니다.'
            })
        return attrs


class SetMenuItemOutputSerializer(serializers.ModelSerializer):
    """세트메뉴 구성 항목 출력용"""
    
    menu_id = serializers.IntegerField(source='menu.id', read_only=True)
    base_price = serializers.DecimalField(
        source='menu.price', 
        max_digits=10, 
        decimal_places=0, 
        read_only=True
    )
    stock = serializers.IntegerField(source='menu.stock', read_only=True)
    
    class Meta:
        model = SetMenuItem
        fields = ['menu_id', 'quantity', 'base_price', 'stock']


class SetMenuItemInputSerializer(serializers.Serializer):
    """SetMenuItem 입력용 직렬화"""
    
    menu_id = serializers.IntegerField(
        error_messages={
            'required': 'menu_id는 필수입니다.',
            'invalid': 'menu_id는 정수여야 합니다.',
        }
    )
    quantity = serializers.IntegerField(
        default=1,
        min_value=1,
        error_messages={
            'min_value': 'quantity는 1 이상이어야 합니다.',
            'invalid': 'quantity는 정수여야 합니다.',
        }
    )
    
    def validate_menu_id(self, value):
        """menu_id가 실제 DB에 존재하는지 확인"""
        if not Menu.objects.filter(id=value).exists():
            raise serializers.ValidationError(f'menu_id {value}에 해당하는 메뉴가 존재하지 않습니다.')
        return value


class SetMenuSerializer(serializers.ModelSerializer):
    """세트메뉴 직렬화 (등록/응답용)"""
    
    # 입력 필드
    name = serializers.CharField(
        max_length=20,
        min_length=1,
        error_messages={
            'blank': '세트메뉴 이름은 필수 항목입니다.',
            'required': '세트메뉴 이름은 필수 항목입니다.',
            'max_length': '세트메뉴 이름은 20자 이하여야 합니다.',
            'min_length': '세트메뉴 이름은 빈 문자열일 수 없습니다.',
        }
    )
    description = serializers.CharField(
        max_length=30,
        required=False,
        allow_blank=True,
        allow_null=True,
        error_messages={
            'max_length': '설명은 30자 이하여야 합니다.',
        }
    )
    price = serializers.IntegerField(
        min_value=0,
        error_messages={
            'min_value': '가격은 0원 이상이어야 합니다.',
            'invalid': '가격은 정수여야 합니다.',
            'required': '가격은 필수 항목입니다.',
        }
    )
    set_items = serializers.ListField(
        child=serializers.DictField(),
        write_only=True,
        error_messages={
            'not_a_list': 'set_items는 배열([]) 형식이어야 합니다.',
            'required': 'set_items는 필수 항목입니다.',
        }
    )
    image = CompressedImageField(
        required=False,
        allow_null=True,
        error_messages={
            'invalid_image': '유효한 이미지 파일이 아닙니다.',
        }
    )
    
    # 출력 필드
    set_id = serializers.IntegerField(source='id', read_only=True)
    booth_id = serializers.IntegerField(source='booth.pk', read_only=True)
    set_items_output = SetMenuItemOutputSerializer(source='items', many=True, read_only=True)
    origin_price = serializers.SerializerMethodField()
    is_soldout = serializers.SerializerMethodField()
    
    class Meta:
        model = SetMenu
        fields = [
            'set_id', 'booth_id', 'name', 'category', 'description',
            'price', 'image', 'set_items', 'set_items_output',
            'origin_price', 'is_soldout', 'created_at', 'updated_at'
        ]
        read_only_fields = ['set_id', 'booth_id', 'category', 'created_at', 'updated_at']
    
    def get_origin_price(self, obj):
        """구성품의 base_price * quantity 합계"""
        total = 0
        for item in obj.items.all():
            total += int(item.menu.price) * item.quantity
        return total
    
    def get_is_soldout(self, obj):
        """구성 메뉴 중 하나라도 stock<=0이면 품절"""
        for item in obj.items.all():
            if item.menu.stock <= 0:
                return True
        return False
    
    def validate_set_items(self, value):
        """세트 구성 항목 유효성 검사"""
        # 빈 배열 체크
        if not value or len(value) == 0:
            raise serializers.ValidationError('최소 1개 이상의 메뉴가 포함되어야 합니다.')
        
        # 각 항목 검증
        validated_items = []
        for idx, item in enumerate(value):
            if not isinstance(item, dict):
                raise serializers.ValidationError(f'set_items[{idx}]는 객체({{}}) 형태여야 합니다.')
            
            item_serializer = SetMenuItemInputSerializer(data=item)
            if not item_serializer.is_valid():
                raise serializers.ValidationError({f'set_items[{idx}]': item_serializer.errors})
            
            validated_items.append(item_serializer.validated_data)
        
        return validated_items
    
    def to_representation(self, instance):
        """응답 포맷 조정 (set_items_output -> set_items)"""
        data = super().to_representation(instance)
        # set_items_output을 set_items로 매핑
        data['set_items'] = data.pop('set_items_output', [])
        return data


class SetMenuUpdateSerializer(serializers.ModelSerializer):
    """세트메뉴 수정용 직렬화 (partial update)"""
    
    # 입력 필드 (모두 optional)
    name = serializers.CharField(
        max_length=20,
        min_length=1,
        required=False,
        error_messages={
            'blank': '세트메뉴 이름은 빈 문자열일 수 없습니다.',
            'max_length': '세트메뉴 이름은 20자 이하여야 합니다.',
            'min_length': '세트메뉴 이름은 빈 문자열일 수 없습니다.',
        }
    )
    description = serializers.CharField(
        max_length=30,
        required=False,
        allow_blank=True,
        allow_null=True,
        error_messages={
            'max_length': '설명은 30자 이하여야 합니다.',
        }
    )
    price = serializers.IntegerField(
        min_value=0,
        required=False,
        error_messages={
            'min_value': '수정할 가격은 0원 이상이어야 합니다.',
            'invalid': '가격은 정수여야 합니다.',
        }
    )
    set_items = serializers.ListField(
        child=serializers.DictField(),
        required=False,
        error_messages={
            'not_a_list': 'set_items는 배열([]) 형식이어야 합니다.',
        }
    )
    image_delete = serializers.BooleanField(
        required=False,
        default=False,
        write_only=True,
    )
    
    # 출력 필드
    set_id = serializers.IntegerField(source='id', read_only=True)
    booth_id = serializers.IntegerField(source='booth.pk', read_only=True)
    set_items_output = SetMenuItemOutputSerializer(source='items', many=True, read_only=True)
    origin_price = serializers.SerializerMethodField()
    is_soldout = serializers.SerializerMethodField()
    
    class Meta:
        model = SetMenu
        fields = [
            'set_id', 'booth_id', 'name', 'category', 'description',
            'price', 'image', 'image_delete', 'set_items', 'set_items_output',
            'origin_price', 'is_soldout', 'created_at', 'updated_at'
        ]
        read_only_fields = ['set_id', 'booth_id', 'category', 'image', 'created_at', 'updated_at']
    
    def get_origin_price(self, obj):
        """구성품의 base_price * quantity 합계"""
        total = 0
        for item in obj.items.all():
            total += int(item.menu.price) * item.quantity
        return total
    
    def get_is_soldout(self, obj):
        """구성 메뉴 중 하나라도 stock<=0이면 품절"""
        for item in obj.items.all():
            if item.menu.stock <= 0:
                return True
        return False
    
    def validate_set_items(self, value):
        """세트 구성 항목 유효성 검사"""
        # 빈 배열 체크 (수정 시에도 최소 1개 필요)
        if not value or len(value) == 0:
            raise serializers.ValidationError('최소 1개 이상의 메뉴가 포함되어야 합니다.')
        
        # 각 항목 검증
        validated_items = []
        for idx, item in enumerate(value):
            if not isinstance(item, dict):
                raise serializers.ValidationError(f'set_items[{idx}]는 객체({{}}) 형태여야 합니다.')
            
            item_serializer = SetMenuItemInputSerializer(data=item)
            if not item_serializer.is_valid():
                raise serializers.ValidationError({f'set_items[{idx}]': item_serializer.errors})
            
            validated_items.append(item_serializer.validated_data)
        
        return validated_items
    
    def validate(self, attrs):
        """이미지 수정 시도 방지"""
        request = self.context.get('request')
        if request and hasattr(request, 'data'):
            if 'image' in request.data and request.data.get('image'):
                raise serializers.ValidationError({
                    'image': '이미지는 수정할 수 없습니다. image_delete로 삭제만 가능합니다.'
                })
        return attrs
    
    def to_representation(self, instance):
        """응답 포맷 조정 (set_items_output -> set_items)"""
        data = super().to_representation(instance)
        data['set_items'] = data.pop('set_items_output', [])
        return data
