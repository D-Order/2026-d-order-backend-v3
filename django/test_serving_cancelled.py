#!/usr/bin/env python3
"""
서빙 취소(롤백) Redis 구독 로직 검증
- OrderService.handle_serving_cancelled() 메서드 테스트
- spring:booth:{booth_id}:order:cooked 채널 처리 검증
"""

import os
import django
import json
from datetime import datetime

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "project.settings")
django.setup()

from django.utils import timezone
from django.contrib.auth.models import User
from order.models import Order, OrderItem
from table.models import Table, TableUsage
from booth.models import Booth
from menu.models import Menu
from order.services import OrderService


def setup_test_data(user_id=None, table_num=1):
    """테스트 데이터 생성"""
    import random
    # User 생성 (Booth pk 용)
    if user_id is None:
        user_id = random.randint(10000, 99999)
    
    user, _ = User.objects.get_or_create(
        username=f"testuser{user_id}",
        defaults={"email": f"test{user_id}@test.com"}
    )
    
    booth, _ = Booth.objects.get_or_create(
        user=user,
        defaults={
            "name": f"테스트 부스{user_id}",
            "account": "1234567890",
            "bank": "국민은행",
            "depositor": "김테스트",
            "table_max_cnt": 10,
            "table_limit_hours": 2.5,
        }
    )
    
    # 기존 테이블이 있으면 삭제 후 다시 생성
    Table.objects.filter(booth=booth, table_num=table_num).delete()
    table = Table.objects.create(booth=booth, table_num=table_num)
    table_usage = TableUsage.objects.create(table=table, started_at=timezone.now())
    
    menu = Menu.objects.create(
        booth=booth,
        name="테스트 메뉴",
        description="설명",
        price=10000,
        category="MENU"
    )
    
    order = Order.objects.create(
        table_usage=table_usage,
        order_price=10000,
        order_status="PAID"
    )
    
    order_item = OrderItem.objects.create(
        order=order,
        menu=menu,
        quantity=1,
        fixed_price=10000,
        status="SERVED",
        served_at=timezone.now()
    )
    
    return booth, table, table_usage, menu, order, order_item


def test_serving_cancelled_basic():
    """기본 서빙 취소 테스트"""
    print("\n" + "="*60)
    print("TEST 1: 기본 서빙 취소 (SERVED → COOKED)")
    print("="*60)
    
    booth, table, table_usage, menu, order, order_item = setup_test_data(user_id=1, table_num=1)
    
    event_data = {
        "order_item_id": order_item.id,
        "booth_id": booth.user_id,
        "reason": "Robot error",
        "pushed_at": datetime.now().isoformat()
    }
    
    print(f"\n📋 테스트 데이터:")
    print(f"  - OrderItem ID: {order_item.id}")
    print(f"  - 초기 상태: {order_item.status}")
    print(f"  - Booth ID: {booth.user_id}")
    
    result = OrderService.handle_serving_cancelled(event_data)
    
    # OrderItem 새로고침
    order_item.refresh_from_db()
    
    print(f"\n📤 처리 결과:")
    print(f"  - Result: {result['result']}")
    print(f"  - Old Status: {result.get('old_status')}")
    print(f"  - New Status: {result.get('new_status')}")
    print(f"  - Reason: {result.get('reason')}")
    
    print(f"\n✅ 검증:")
    checks = [
        ("result == 'success'", result['result'] == 'success'),
        ("old_status == 'SERVED'", result.get('old_status') == 'SERVED'),
        ("new_status == 'COOKED'", result.get('new_status') == 'COOKED'),
        (f"DB status == 'COOKED'", order_item.status == 'COOKED'),
        ("served_at 유지됨", order_item.served_at is not None),
    ]
    
    for check_name, check_result in checks:
        status = "✓" if check_result else "✗"
        print(f"  {status} {check_name}")
    
    all_passed = all(check[1] for check in checks)
    return all_passed


def test_serving_cancelled_not_found():
    """OrderItem 없을 때 테스트"""
    print("\n" + "="*60)
    print("TEST 2: OrderItem 없음 (not_found)")
    print("="*60)
    
    user, _ = User.objects.get_or_create(
        username="testuser2",
        defaults={"email": "test2@test.com"}
    )
    booth, _ = Booth.objects.get_or_create(
        user=user,
        defaults={
            "name": "테스트 부스2",
            "account": "1234567890",
            "bank": "국민은행",
            "depositor": "김테스트",
            "table_max_cnt": 10,
            "table_limit_hours": 2.5,
        }
    )
    
    event_data = {
        "order_item_id": 99999,  # 없는 ID
        "booth_id": booth.user_id,
    }
    
    print(f"\n📋 테스트 데이터:")
    print(f"  - OrderItem ID: {event_data['order_item_id']} (존재하지 않음)")
    print(f"  - Booth ID: {event_data['booth_id']}")
    
    result = OrderService.handle_serving_cancelled(event_data)
    
    print(f"\n📤 처리 결과:")
    print(f"  - Result: {result['result']}")
    
    print(f"\n✅ 검증:")
    check = result['result'] == 'not_found'
    status = "✓" if check else "✗"
    print(f"  {status} result == 'not_found': {check}")
    
    return check


def test_serving_cancelled_invalid_status():
    """이미 COOKED 상태인데 롤백 시도"""
    print("\n" + "="*60)
    print("TEST 3: 이미 COOKED 상태 (invalid_status)")
    print("="*60)
    
    booth, table, table_usage, menu, order, order_item = setup_test_data(user_id=3, table_num=3)
    order_item.status = "COOKED"
    order_item.save()
    
    event_data = {
        "order_item_id": order_item.id,
        "booth_id": booth.user_id,
    }
    
    print(f"\n📋 테스트 데이터:")
    print(f"  - OrderItem ID: {order_item.id}")
    print(f"  - 초기 상태: {order_item.status}")
    print(f"  - Booth ID: {booth.user_id}")
    
    result = OrderService.handle_serving_cancelled(event_data)
    
    print(f"\n📤 처리 결과:")
    print(f"  - Result: {result['result']}")
    
    print(f"\n✅ 검증:")
    check = result['result'] == 'invalid_status'
    status = "✓" if check else "✗"
    print(f"  {status} result == 'invalid_status': {check}")
    
    return check


def test_serving_cancelled_forbidden():
    """부스 권한 없을 때"""
    print("\n" + "="*60)
    print("TEST 4: 부스 권한 없음 (forbidden)")
    print("="*60)
    
    # 부스1
    user1, _ = User.objects.get_or_create(
        username="testuser4a",
        defaults={"email": "test4a@test.com"}
    )
    booth1, _ = Booth.objects.get_or_create(
        user=user1,
        defaults={
            "name": "부스1",
            "account": "1234567890",
            "bank": "국민은행",
            "depositor": "김테스트",
            "table_max_cnt": 10,
            "table_limit_hours": 2.5,
        }
    )
    
    # 부스2
    user2, _ = User.objects.get_or_create(
        username="testuser4b",
        defaults={"email": "test4b@test.com"}
    )
    booth2, _ = Booth.objects.get_or_create(
        user=user2,
        defaults={
            "name": "부스2",
            "account": "1234567890",
            "bank": "국민은행",
            "depositor": "김테스트",
            "table_max_cnt": 10,
            "table_limit_hours": 2.5,
        }
    )
    
    table = Table.objects.create(booth=booth1, table_num=4)
    table_usage = TableUsage.objects.create(table=table, started_at=timezone.now())
    
    menu = Menu.objects.create(
        booth=booth1,
        name="테스트 메뉴",
        description="설명",
        price=10000,
        category="MENU"
    )
    
    order = Order.objects.create(
        table_usage=table_usage,
        order_price=10000,
        order_status="PAID"
    )
    
    order_item = OrderItem.objects.create(
        order=order,
        menu=menu,
        quantity=1,
        fixed_price=10000,
        status="SERVED",
        served_at=timezone.now()
    )
    
    event_data = {
        "order_item_id": order_item.id,
        "booth_id": booth2.user_id,  # 다른 부스
    }
    
    print(f"\n📋 테스트 데이터:")
    print(f"  - OrderItem이 속한 Booth ID: {booth1.user_id}")
    print(f"  - 요청한 Booth ID: {booth2.user_id}")
    
    result = OrderService.handle_serving_cancelled(event_data)
    
    print(f"\n📤 처리 결과:")
    print(f"  - Result: {result['result']}")
    
    print(f"\n✅ 검증:")
    check = result['result'] == 'forbidden'
    status = "✓" if check else "✗"
    print(f"  {status} result == 'forbidden': {check}")
    
    return check


def test_serving_cancelled_missing_fields():
    """필수 필드 누락"""
    print("\n" + "="*60)
    print("TEST 5: 필수 필드 누락 (missing_fields)")
    print("="*60)
    
    user, _ = User.objects.get_or_create(
        username="testuser5",
        defaults={"email": "test5@test.com"}
    )
    booth, _ = Booth.objects.get_or_create(
        user=user,
        defaults={
            "name": "테스트 부스5",
            "account": "1234567890",
            "bank": "국민은행",
            "depositor": "김테스트",
            "table_max_cnt": 10,
            "table_limit_hours": 2.5,
        }
    )
    
    event_data = {
        "booth_id": booth.user_id,
        # order_item_id 누락
    }
    
    print(f"\n📋 테스트 데이터:")
    print(f"  - order_item_id: 누락됨")
    print(f"  - booth_id: {booth.user_id}")
    
    result = OrderService.handle_serving_cancelled(event_data)
    
    print(f"\n📤 처리 결과:")
    print(f"  - Result: {result['result']}")
    
    print(f"\n✅ 검증:")
    check = result['result'] == 'missing_fields'
    status = "✓" if check else "✗"
    print(f"  {status} result == 'missing_fields': {check}")
    
    return check


if __name__ == "__main__":
    print("\n" + "="*70)
    print("🤖 서빙 취소 Redis 구독 로직 검증")
    print("="*70)
    
    results = []
    
    try:
        results.append(("기본 서빙 취소", test_serving_cancelled_basic()))
        results.append(("OrderItem 없음", test_serving_cancelled_not_found()))
        results.append(("잘못된 상태", test_serving_cancelled_invalid_status()))
        results.append(("부스 권한 없음", test_serving_cancelled_forbidden()))
        results.append(("필수 필드 누락", test_serving_cancelled_missing_fields()))
    except Exception as e:
        print(f"\n❌ 테스트 중 오류: {e}")
        import traceback
        traceback.print_exc()
    
    print("\n" + "="*70)
    print("📊 테스트 결과 요약")
    print("="*70)
    
    for test_name, passed in results:
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"  {status}: {test_name}")
    
    total_passed = sum(1 for _, p in results if p)
    total_tests = len(results)
    
    print(f"\n총 {total_tests}개 테스트 중 {total_passed}개 통과")
    
    if total_passed == total_tests:
        print("\n🎉 모든 검증 통과!")
    else:
        print(f"\n⚠️  {total_tests - total_passed}개 테스트 실패")
