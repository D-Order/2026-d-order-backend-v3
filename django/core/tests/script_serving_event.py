"""
스프링부트 서빙 이벤트 시뮬레이션 테스트
- spring:booth:1:order:serving  (서빙 수락)
- spring:booth:1:order:served   (서빙 완료)

사용법:
  python core/test_serving_event.py serving 12   # id=12를 SERVING으로
  python core/test_serving_event.py served 12    # id=12를 SERVED로
"""
import os, sys, json, django

current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.join(current_dir, "..")
sys.path.insert(0, project_root)
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "project.settings")
django.setup()

from django.utils import timezone
from core.redis_client import get_redis_client

BOOTH_ID = 1


def publish_serving_event(action: str, order_item_id: int):
    client = get_redis_client()

    if action == "serving":
        payload = {
            "order_item_id": order_item_id,
            "status": "serving",
            "catched_by": "Robot_03",
            "pushed_at": timezone.localtime().isoformat(),
        }
    elif action == "served":
        payload = {
            "order_item_id": order_item_id,
            "status": "served",
            "pushed_at": timezone.localtime().isoformat(),
        }
    else:
        print(f"❌ 알 수 없는 action: {action} (serving / served 중 선택)")
        return

    channel = f"spring:booth:{BOOTH_ID}:order:{action}"
    message = json.dumps(payload, ensure_ascii=False)

    client.publish(channel, message)
    print(f"✅ Redis Pub 완료")
    print(f"   채널: {channel}")
    print(f"   데이터: {message}")


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("사용법: python core/test_serving_event.py <serving|served> <order_item_id>")
        print("예시:   python core/test_serving_event.py serving 12")
        sys.exit(1)

    action = sys.argv[1]
    item_id = int(sys.argv[2])
    publish_serving_event(action, item_id)
