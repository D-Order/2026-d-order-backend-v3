"""
테이블 초기화 Redis 발행 테스트 스크립트
사용법:
  단일 테이블:   python core/tests/script_table_reset_publish.py <booth_id> <table_num>
  여러 테이블:   python core/tests/script_table_reset_publish.py <booth_id> <table_num1> <table_num2> ...

예시:
  python core/tests/script_table_reset_publish.py 1 3
  python core/tests/script_table_reset_publish.py 1 3 4 5
"""
import redis
import json
import sys

if len(sys.argv) < 3:
    print("사용법: python core/tests/script_table_reset_publish.py <booth_id> <table_num> [table_num2 ...]")
    sys.exit(1)

booth_id = sys.argv[1]
table_nums = [int(n) for n in sys.argv[2:]]

r = redis.Redis(host='localhost', port=6379, db=0, password='redispassword', decode_responses=True)

# 테이블당 1건씩 django:booth:{id}:order:reset 으로 발행
for table_num in table_nums:
    channel = f"django:booth:{booth_id}:order:reset"
    data = {"table_num": table_num}
    message_json = json.dumps(data, ensure_ascii=False)
    receivers = r.publish(channel, message_json)

    print(f"✅ 테이블 {table_num} 초기화 이벤트 발행 완료")
    print(f"   채널: {channel}")
    print(f"   데이터: {message_json}")
    print(f"   수신자 수: {receivers}명")

    if receivers == 0:
        print("   ⚠️  수신자 0명 → Spring이 구독 중이지 않을 수 있어요.")
    else:
        print(f"   → Spring에서 메세지를 받았어요!")
    print()
