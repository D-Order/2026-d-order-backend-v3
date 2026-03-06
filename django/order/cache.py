"""
오늘 매출 Redis 캐시 헬퍼

캐시 키: booth:{booth_id}:today_revenue:{YYYY-MM-DD}
TTL    : 자정까지 (일 경계 자동 만료)

공개 API:
  get_today_revenue(booth_id)           → 캐시 우선 조회, 미스 시 DB 초기화
  update_today_revenue(booth_id, delta) → INCRBY (캐시 미스 시 DB 초기화 후 적용)
"""

import logging
from django.utils import timezone

logger = logging.getLogger(__name__)


# ──────────────────────────────────────────────
# 내부 헬퍼
# ──────────────────────────────────────────────

def _cache_key(booth_id: int) -> str:
    return f"booth:{booth_id}:today_revenue:{timezone.localdate().isoformat()}"


def _ttl_until_midnight() -> int:
    """오늘 자정까지 남은 초 (최소 1초)"""
    from datetime import timedelta
    now = timezone.localtime()
    midnight = (now + timedelta(days=1)).replace(
        hour=0, minute=0, second=0, microsecond=0
    )
    return max(int((midnight - now).total_seconds()), 1)


def _query_db(booth_id: int) -> int:
    """DB에서 오늘(로컬 날짜) PAID/COMPLETED 주문의 order_price 합산"""
    from order.models import Order
    from django.db.models import Sum

    return (
        Order.objects
        .filter(
            order_status__in=["PAID", "COMPLETED"],
            table_usage__table__booth_id=booth_id,
            created_at__date=timezone.localdate(),
        )
        .aggregate(total=Sum("order_price"))["total"]
    ) or 0


def _write_cache(booth_id: int, amount: int) -> None:
    try:
        from core.redis_client import get_redis_client
        get_redis_client().setex(_cache_key(booth_id), _ttl_until_midnight(), amount)
    except Exception as e:
        logger.warning(f"[Revenue Cache] 쓰기 실패 booth={booth_id}: {e}")


# ──────────────────────────────────────────────
# 공개 API
# ──────────────────────────────────────────────

def get_today_revenue(booth_id: int) -> int:
    """
    오늘 매출 조회 (캐시 우선).

    캐시 히트 → 바로 반환
    캐시 미스 → DB 쿼리 후 캐시 저장 → 반환
    Redis 장애 → DB 쿼리 결과 직접 반환
    """
    try:
        from core.redis_client import get_redis_client
        value = get_redis_client().get(_cache_key(booth_id))
        if value is not None:
            return int(value)
    except Exception as e:
        logger.warning(f"[Revenue Cache] 조회 실패 booth={booth_id}: {e}")

    amount = _query_db(booth_id)
    _write_cache(booth_id, amount)
    return amount


def update_today_revenue(booth_id: int, delta: int) -> int:
    """
    오늘 매출 캐시를 delta 만큼 원자적으로 증감.

    delta > 0 : 주문 생성 (order_price 만큼 증가)
    delta < 0 : 주문 취소 (refund_amount 만큼 감소)

    캐시 히트 → INCRBY (원자적, TTL 갱신)
    캐시 미스 → DB 초기화 후 delta 적용
    Redis 장애 → DB 쿼리 결과 반환

    Returns: 갱신 후 오늘 매출 (int)
    """
    try:
        from core.redis_client import get_redis_client
        redis = get_redis_client()
        key = _cache_key(booth_id)

        if redis.exists(key):
            new_value = int(redis.incrby(key, delta))
            redis.expire(key, _ttl_until_midnight())
            return new_value
    except Exception as e:
        logger.warning(f"[Revenue Cache] INCRBY 실패 booth={booth_id}: {e}")

    # 캐시 미스 또는 Redis 장애 → DB 초기화 (delta 포함 최신 값 반환)
    return get_today_revenue(booth_id)
