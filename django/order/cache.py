"""
오늘 매출 Redis 캐시 헬퍼

캐시 키: booth:{booth_id}:today_revenue:{YYYY-MM-DD}
TTL    : 자정까지 (일 경계 자동 만료)

공개 API:
  get_today_revenue(booth_id, for_date=None)
      → 캐시 우선 조회, 미스 시 DB 집계 후 SET NX EX
  update_today_revenue(booth_id, delta, for_date=None)
      → Lua 스크립트로 INCRBY+EXPIRE 원자 처리, 미스 시 DB 베이스라인 + INCRBY
  invalidate_today_revenue(booth_id, for_date=None)
      → 캐시 삭제 (다음 조회 시 DB 재계산)
"""

import logging
from datetime import date as date_cls, datetime, timedelta

from django.utils import timezone

logger = logging.getLogger(__name__)


# ──────────────────────────────────────────────
# Lua: 키가 존재할 때만 INCRBY + EXPIRE
# 반환: 새 값 (int) 또는 nil
# ──────────────────────────────────────────────
_LUA_INCR_IF_EXISTS = """
if redis.call('EXISTS', KEYS[1]) == 1 then
  local v = redis.call('INCRBY', KEYS[1], ARGV[1])
  redis.call('EXPIRE', KEYS[1], ARGV[2])
  return v
else
  return nil
end
"""


# ──────────────────────────────────────────────
# 내부 헬퍼
# ──────────────────────────────────────────────

def _resolve_date(for_date):
    """for_date(None|date|datetime) → 로컬 date"""
    if for_date is None:
        return timezone.localdate()
    if isinstance(for_date, datetime):
        if timezone.is_aware(for_date):
            return timezone.localtime(for_date).date()
        return for_date.date()
    if isinstance(for_date, date_cls):
        return for_date
    raise TypeError(f"for_date must be date/datetime/None, got {type(for_date)!r}")


def _cache_key(booth_id: int, for_date=None) -> str:
    return f"booth:{booth_id}:today_revenue:{_resolve_date(for_date).isoformat()}"


def _ttl_until_next_midnight(target_date) -> int:
    """target_date 다음 자정까지 남은 초 (오늘이 아니면 즉시 만료 직전인 1초)"""
    today = timezone.localdate()
    if target_date != today:
        # 과거 날짜 키는 짧게 유지 (정합성 확보 후 자연 만료)
        return 60
    now = timezone.localtime()
    midnight = (now + timedelta(days=1)).replace(
        hour=0, minute=0, second=0, microsecond=0
    )
    return max(int((midnight - now).total_seconds()), 1)


def _query_db(booth_id: int, for_date=None) -> int:
    """대상 날짜의 PAID/COMPLETED 주문의 order_price 합산"""
    from order.models import Order
    from django.db.models import Sum

    target = _resolve_date(for_date)
    return (
        Order.objects
        .filter(
            order_status__in=["PAID", "COMPLETED"],
            table_usage__table__booth_id=booth_id,
            created_at__date=target,
        )
        .aggregate(total=Sum("order_price"))["total"]
    ) or 0


# ──────────────────────────────────────────────
# 공개 API
# ──────────────────────────────────────────────

def get_today_revenue(booth_id: int, for_date=None) -> int:
    """
    오늘(또는 지정 날짜) 매출 조회.

    캐시 히트 → 바로 반환
    캐시 미스 → DB 집계 → SET NX EX 베이스라인 → 반환
    Redis 장애 → DB 결과 직접 반환
    """
    target = _resolve_date(for_date)
    key = _cache_key(booth_id, target)

    try:
        from core.redis_client import get_redis_client
        redis = get_redis_client()
        value = redis.get(key)
        if value is not None:
            return int(value)
    except Exception as e:
        logger.warning(f"[Revenue Cache] 조회 실패 booth={booth_id} date={target}: {e}")
        redis = None

    amount = _query_db(booth_id, target)

    if redis is not None:
        try:
            # 동시 미스 경합에서 한 쪽만 베이스라인을 채택하도록 NX 사용
            redis.set(key, amount, ex=_ttl_until_next_midnight(target), nx=True)
        except Exception as e:
            logger.warning(f"[Revenue Cache] 베이스라인 저장 실패 booth={booth_id} date={target}: {e}")

    return amount


def update_today_revenue(booth_id: int, delta: int, for_date=None) -> int:
    """
    매출 캐시를 delta 만큼 원자적으로 증감.

    delta > 0 : 주문 생성 (order_price 만큼 증가)
    delta < 0 : 주문 취소 (refund_amount 만큼 감소)

    1) Lua 스크립트로 "키 존재 시 INCRBY+EXPIRE" 단일 명령 시도
    2) 키 부재(nil) 시: _query_db로 베이스라인 산출 → SET NX EX → INCRBY delta → EXPIRE
       (NX 실패 시 다른 워커가 베이스라인을 박은 것이므로 그대로 INCRBY 진행)
    3) Redis 장애: DB 재계산 결과 반환 (캐시 미반영)

    Returns: 갱신 후 매출 (int)
    """
    target = _resolve_date(for_date)
    key = _cache_key(booth_id, target)
    ttl = _ttl_until_next_midnight(target)

    try:
        from core.redis_client import get_redis_client
        redis = get_redis_client()

        result = redis.eval(_LUA_INCR_IF_EXISTS, 1, key, delta, ttl)
        if result is not None:
            return int(result)

        # 캐시 부재 → DB 베이스라인 + delta
        baseline = _query_db(booth_id, target)
        # NX로 베이스라인 시도 (실패 시 동시 워커가 이미 박음)
        redis.set(key, baseline, ex=ttl, nx=True)
        new_value = int(redis.incrby(key, delta))
        redis.expire(key, ttl)
        return new_value
    except Exception as e:
        logger.warning(f"[Revenue Cache] update 실패 booth={booth_id} date={target}: {e}")
        return _query_db(booth_id, target)


def invalidate_today_revenue(booth_id: int, for_date=None) -> None:
    """
    매출 캐시를 삭제한다.

    데이터 포맷 등으로 주문이 일괄 삭제된 경우,
    다음 조회 시 DB에서 재계산되도록 캐시를 무효화한다.
    """
    target = _resolve_date(for_date)
    try:
        from core.redis_client import get_redis_client
        get_redis_client().delete(_cache_key(booth_id, target))
    except Exception as e:
        logger.warning(f"[Revenue Cache] 삭제 실패 booth={booth_id} date={target}: {e}")
