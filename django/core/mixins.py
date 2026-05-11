import json
from decimal import Decimal


class KoreanAsyncJsonMixin:
    @classmethod
    async def encode_json(cls, content):  # 반드시 앞에 'async'가 있어야 합니다!
        # Decimal을 float로 변환하는 custom encoder
        def decimal_default(obj):
            if isinstance(obj, Decimal):
                return float(obj)
            raise TypeError(f"Object of type {type(obj)} is not JSON serializable")
        
        return json.dumps(content, ensure_ascii=False, default=decimal_default)