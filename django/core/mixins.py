import json

class KoreanAsyncJsonMixin:
    @classmethod
    async def encode_json(cls, content):  # 반드시 앞에 'async'가 있어야 합니다!
        return json.dumps(content, ensure_ascii=False)