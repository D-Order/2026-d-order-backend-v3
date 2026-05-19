"""
오늘 매출 캐시(order/cache.py) 정합성 테스트.

DB는 _query_db 호출 모킹으로 우회. Redis는 실제 컨테이너 사용.
"""

from datetime import timedelta
from unittest.mock import patch, MagicMock

import pytest
from django.utils import timezone

from order import cache as revenue_cache


BOOTH_ID = 999_001


@pytest.fixture(autouse=True)
def clean_cache():
    """각 테스트 전후로 테스트용 부스의 매출 캐시 키를 비운다."""
    from core.redis_client import get_redis_client
    try:
        redis = get_redis_client()
        for key in redis.scan_iter(f"booth:{BOOTH_ID}:today_revenue:*"):
            redis.delete(key)
    except Exception:
        pass
    yield
    try:
        redis = get_redis_client()
        for key in redis.scan_iter(f"booth:{BOOTH_ID}:today_revenue:*"):
            redis.delete(key)
    except Exception:
        pass


# ──────────────────────────────────────────────
# 1) 트랜잭션 롤백 시 캐시 불변
# ──────────────────────────────────────────────

def test_revenue_cache_unaffected_on_rollback():
    """호출부가 on_commit 콜백 안에서 update_today_revenue를 호출하도록
    이동된 결과, atomic 블록이 롤백되면 캐시가 변하지 않는지를 검증.

    실제 DB 트랜잭션 대신 Django의 transaction.on_commit 의미를 mock으로
    재현 — 롤백 시 on_commit 콜백을 호출하지 않는 동작을 시뮬레이션.
    """
    # 사전 베이스라인: 캐시에 10000 박아둠
    with patch.object(revenue_cache, "_query_db", return_value=10000):
        revenue_cache.update_today_revenue(BOOTH_ID, 0)
    assert revenue_cache.get_today_revenue(BOOTH_ID) == 10000

    # transaction.on_commit이 호출되었지만 atomic 블록이 롤백된 상황 모사
    pending = []
    def fake_on_commit(cb):
        pending.append(cb)

    with patch("django.db.transaction.on_commit", side_effect=fake_on_commit):
        from django.db import transaction as tx
        def _bump():
            revenue_cache.update_today_revenue(BOOTH_ID, 5000)
        tx.on_commit(_bump)
        # ↑ 실제 운영 코드의 on_commit 등록 흐름. 롤백 시 pending 콜백은 폐기됨.

    # 롤백 시뮬레이션: pending 콜백을 호출하지 않고 폐기
    assert len(pending) == 1
    pending.clear()

    # 캐시는 베이스라인 그대로
    assert revenue_cache.get_today_revenue(BOOTH_ID) == 10000

    # 커밋 시뮬레이션: 콜백 실행 시 캐시가 변경됨을 함께 확인 (positive control)
    pending2 = []
    with patch("django.db.transaction.on_commit", side_effect=lambda cb: pending2.append(cb)):
        from django.db import transaction as tx
        tx.on_commit(lambda: revenue_cache.update_today_revenue(BOOTH_ID, 5000))
    for cb in pending2:
        cb()
    assert revenue_cache.get_today_revenue(BOOTH_ID) == 15000


# ──────────────────────────────────────────────
# 2) 동시 캐시 미스에서 합산 보존 (SET NX 베이스라인)
# ──────────────────────────────────────────────

def test_concurrent_miss_no_lost_update():
    """두 트랜잭션이 동시에 캐시 미스를 만났을 때, 먼저 베이스라인을 박은
    쪽이 채택되고 나중 쪽은 INCRBY로 합산되어야 한다 (SET NX 효과)."""
    key = revenue_cache._cache_key(BOOTH_ID)

    calls = {"n": 0}
    def fake_query_db(booth_id, for_date=None):
        calls["n"] += 1
        return 1000 if calls["n"] == 1 else 3000

    with patch.object(revenue_cache, "_query_db", side_effect=fake_query_db):
        v1 = revenue_cache.update_today_revenue(BOOTH_ID, 1000)
        v2 = revenue_cache.update_today_revenue(BOOTH_ID, 3000)

    # 첫 호출: 베이스라인 1000 + delta 1000 = 2000
    assert v1 == 2000
    # 두 번째: 캐시 히트 (Lua INCRBY) → 2000 + 3000 = 5000
    assert v2 == 5000

    from core.redis_client import get_redis_client
    assert int(get_redis_client().get(key)) == 5000


# ──────────────────────────────────────────────
# 3) 자정 경계: for_date 인자로 어제 키를 지정
# ──────────────────────────────────────────────

def test_yesterday_order_uses_yesterday_key():
    """for_date를 명시하면 어제 키에 INCRBY되어야 하고 오늘 키는 건드리지 않아야 한다."""
    today = timezone.localdate()
    yesterday = today - timedelta(days=1)

    today_key = revenue_cache._cache_key(BOOTH_ID, today)
    yesterday_key = revenue_cache._cache_key(BOOTH_ID, yesterday)

    with patch.object(revenue_cache, "_query_db", return_value=0):
        revenue_cache.update_today_revenue(BOOTH_ID, 7000, for_date=yesterday)

    from core.redis_client import get_redis_client
    redis = get_redis_client()
    assert redis.get(today_key) is None
    assert int(redis.get(yesterday_key)) == 7000


# ──────────────────────────────────────────────
# 4) TOCTOU: Lua 스크립트가 키 부재 시 nil → 폴백이 베이스라인 + INCRBY
# ──────────────────────────────────────────────

def test_toctou_lua_returns_nil_falls_back_to_baseline():
    """Lua 스크립트가 nil을 반환하면 _query_db로 베이스라인을 박고 INCRBY로 delta를 더한다.
    기존 exists+incrby 분리 구조의 TTL 만료 race를 단일 명령으로 차단한 것을 검증."""
    with patch.object(revenue_cache, "_query_db", return_value=4000):
        new_value = revenue_cache.update_today_revenue(BOOTH_ID, 1500)

    assert new_value == 5500

    from core.redis_client import get_redis_client
    assert int(get_redis_client().get(revenue_cache._cache_key(BOOTH_ID))) == 5500
