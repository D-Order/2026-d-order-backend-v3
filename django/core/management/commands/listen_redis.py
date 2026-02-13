import json
import re
from django.core.management.base import BaseCommand
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync
from core.redis_client import psubscribe


class Command(BaseCommand):
    help = 'Spring에서 오는 Redis 메시지를 패턴 구독하여 WebSocket으로 브로드캐스트'

    def handle(self, *args, **options):
        self.stdout.write(
            self.style.SUCCESS("Spring 메시지 리스너 시작 (패턴 구독)...")
        )

        channel_layer = get_channel_layer()

        # 패턴 구독: 모든 부스의 이벤트
        pubsub = psubscribe([            
            "booth:*:staffcall:*",   # 아직은 호출 이벤트만 처리
            # "booth:*:table:*",       # 모든 부스의 테이블 이벤트
            # "booth:*:order:*",       # 모든 부스의 주문 이벤트
        ])

        self.stdout.write(
            self.style.SUCCESS("구독 채널 패턴:")
        )
        # self.stdout.write("  - booth:*:order:*")
        self.stdout.write("  - booth:*:staffcall:*")
        # self.stdout.write("  - booth:*:table:*")
        self.stdout.write("")

        for message in pubsub.listen():
            # 패턴 구독은 "pmessage" 타입
            if message["type"] != "pmessage":
                continue

            try:
                pattern = message["pattern"]   # "booth:*:order:*"
                channel = message["channel"]   # "booth:1:order:new"
                data = json.loads(message["data"])

                # 채널명 파싱: booth:1:order:new → booth_id=1, domain=order, action=new
                match = re.match(r"booth:(\d+):(\w+):(\w+)", channel)
                if not match:
                    self.stderr.write(
                        self.style.ERROR(f"잘못된 채널 형식: {channel}")
                    )
                    continue

                booth_id, domain, action = match.groups()

                # WebSocket 그룹명
                group_name = f"booth_{booth_id}"

                # 이벤트 타입: order_new, staffcall_newcall 등
                event_type = f"{domain}_{action}"

                # WebSocket 그룹으로 브로드캐스트
                async_to_sync(channel_layer.group_send)(
                    group_name,
                    {
                        "type": event_type,  # 예시) Consumer의 order_new() 메서드 호출
                        "data": data
                    }
                )

                self.stdout.write(
                    self.style.SUCCESS(
                        f"[{pattern}] {channel} → {group_name}.{event_type}"
                    )
                )
                self.stdout.write(f"  데이터: {data}")

            except json.JSONDecodeError as e:
                self.stderr.write(
                    self.style.ERROR(f"JSON 파싱 실패: {e}")
                )
            except Exception as e:
                self.stderr.write(
                    self.style.ERROR(f"메시지 처리 실패: {e}")
                )
