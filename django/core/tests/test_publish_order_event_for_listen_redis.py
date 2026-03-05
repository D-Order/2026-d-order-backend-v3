"""
Redis 주문 이벤트 발행 테스트 스크립트
사용법:
  주문 생성:  python core/test_publish_order_event_for_listen_redis.py <booth_id> new
  결제 거절:  python core/test_publish_order_event_for_listen_redis.py <booth_id> cancel
"""
import redis
import json
import sys
import uuid
from datetime import datetime

if len(sys.argv) < 2:
    print("사용법: python core/test_publish_order_event_for_listen_redis.py <booth_id> [new|cancel]")
    sys.exit(1)

booth_id = sys.argv[1]
action = sys.argv[2] if len(sys.argv) > 2 else "new"

r = redis.Redis(host='localhost', port=6379, db=0, password='redispassword')

if action == "new":
    # ──── 주문 생성 이벤트 (payment.confirmed) ────
    CHANNEL = f"spring:booth:{booth_id}:order:new"
    event_data = {
        "event_id": str(uuid.uuid4()),
        "event_type": "order.created",
        "version": 1,
        "occurred_at": datetime.now().isoformat(),
        "data": {
            "table_usage_id": 1,
            "cart_id": 1,
            "staff_call_id": 1,
            "status": "completed",
            "total_price": 10000,
            "original_total_price": 12000,
            "coupon_id": None,
            "total_discount": 2000
        }
    }
    r.publish(CHANNEL, json.dumps(event_data))
    print(f"✅ 주문 생성 이벤트 발행 → {CHANNEL}")
    print(f"   event_id: {event_data['event_id']}")
    print(f"   cart_id: 1, total_price: 10000")

elif action == "cancel":
    # ──── 결제거절 이벤트 (payment.rejected) ────
    # 운영자가 결제 확인 전 취소 → Cart.status를 active로 복구
    CHANNEL = f"spring:booth:{booth_id}:order:cancel"
    event_data = {
        "event_id": str(uuid.uuid4()),
        "event_type": "payment.rejected",
        "version": 1,
        "occurred_at": datetime.now().isoformat(),
        "data": {
            "staff_call_id": 1,
            "cart_id": 1,
            "table_usage_id": 1
        }
    }
    r.publish(CHANNEL, json.dumps(event_data))
    print(f"✅ 결제거절 이벤트 발행 → {CHANNEL}")
    print(f"   event_id: {event_data['event_id']}")
    print(f"   cart_id: 1 → Cart.status = active로 복구 예상")

else:
    print(f"❌ 알 수 없는 액션: {action}")
    print("   사용 가능: new, cancel")
    sys.exit(1)
