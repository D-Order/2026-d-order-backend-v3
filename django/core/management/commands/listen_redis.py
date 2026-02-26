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

        # 패턴 구독: Spring에서 오는 메시지만 수신 (spring: 접두사)
        # Django가 발행한 메시지(django: 접두사)는 구독하지 않음
        pubsub = psubscribe([
            "spring:booth:*:staffcall:*",   # Spring → Django 호출 이벤트
            "spring:booth:*:tables:*",       # Spring → Django 테이블 이벤트
            # "spring:booth:*:order:*",       # Spring → Django 주문 이벤트
        ])

        self.stdout.write(
            self.style.SUCCESS("구독 채널 패턴:")
        )
        # self.stdout.write("  - spring:booth:*:order:*")
        self.stdout.write("  - spring:booth:*:staffcall:*")
        self.stdout.write("  - spring:booth:*:tables:*")
        self.stdout.write("")

        for message in pubsub.listen():
            # 패턴 구독은 "pmessage" 타입
            if message["type"] != "pmessage":
                continue

            try:
                pattern = message["pattern"]   # "spring:booth:*:order:*"
                channel = message["channel"]   # "spring:booth:1:order:new"
                data = json.loads(message["data"])

                # 채널명 파싱: booth:1:order:new → booth_id=1, domain=order, action=new
                match = re.match(r"spring:booth:(\d+):(\w+):(\w+)", channel)
                if not match:
                    self.stderr.write(
                        self.style.ERROR(f"잘못된 채널 형식: {channel}")
                    )
                    continue

                booth_id, domain, action = match.groups()

                # WebSocket 그룹명
                group_name = f"booth_{booth_id}.{domain}"

                # 이벤트 타입: order_new, staffcall_newcall 등
                event_type = f"{action}"

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
