import redis
import json
import logging
from django.conf import settings

logger = logging.getLogger(__name__)

_client = None

def get_redis_client():
    global _client
    if _client is None:
        try:
            _client = redis.StrictRedis(
                host=settings.REDIS_HOST,
                port=int(settings.REDIS_PORT),
                # db=0,  # Redis DB 0 사용 (필요시 설정 추가)
                password=settings.REDIS_PASSWORD,
                decode_responses=True
            )
        except Exception as e:
            logger.error(f"Failed to create Redis client: {e}")
            raise
    return _client

def publish(channel: str, data: dict):
    client = get_redis_client()

    try:
        client = get_redis_client()
        message_json = json.dumps(data, ensure_ascii=False)
        channel = f"django:{channel}"
        logger.info(channel)
        client.publish(channel, message_json)
        logger.info(f"[Redis Pub] {channel} : {message_json}")
    except Exception as e:
        logger.error(f"[Redis Pub] Failed to publish message: {channel} : {e}")


def subscribe(channels: list):
    """
    Redis 일반 구독 (패턴 구독 아님)

    Args:
        channels: 구독할 채널 목록 리스트 형식으로 입력할것.

    Returns:
        PubSub 객체

    Example:
        pubsub = subscribe(["booth:1:order:new", "booth:1:order:status"])
        for message in pubsub.listen():
            if message["type"] == "message":
                data = json.loads(message["data"])
    """
    client = get_redis_client()
    pubsub = client.pubsub()
    pubsub.subscribe(*channels)
    return pubsub

def psubscribe(patterns: list):
    """
    Redis 패턴 구독 (와일드카드 패턴 매칭)

    Args:
        patterns: 구독할 패턴 목록 (와일드카드 * 사용 가능)

    Returns:
        PubSub 객체

    Example:
        # 모든 부스의 주문 이벤트 구독
        pubsub = psubscribe(["booth:*:order:*", "booth:*:call:*"])
        for message in pubsub.listen():
            if message["type"] == "pmessage":
                pattern = message["pattern"]   # "booth:*:order:*"
                channel = message["channel"]   # "booth:1:order:new"
                data = json.loads(message["data"])
    """
    client = get_redis_client()
    pubsub = client.pubsub()
    pubsub.psubscribe(*patterns)
    return pubsub