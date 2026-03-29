"""
테스트 데이터 생성 Management Command

Usage:
    python manage.py seed_data           # User 3개 기반으로 데이터 생성
    python manage.py seed_data --reset   # 기존 시드 데이터 삭제 후 재생성

부스 구성:
    멋쟁이사자처럼  → 테이블 10개 / 한식 메뉴
    멋진호랑이들    → 테이블 25개 / 양식 메뉴
    멋스러운사자들  → 테이블 50개 / 중식 메뉴
"""

import uuid
import random
from decimal import Decimal
from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from django.utils import timezone
from django.db import transaction


# ──────────────────────────────────────────────────────────────
# 부스별 고정 설정
# ──────────────────────────────────────────────────────────────
BOOTH_CONFIGS = [
    {
        "name": "멋쟁이사자처럼",
        "table_count": 10,
        "bank": "국민은행",
        "seat_type": "NO",
        "seat_fee_person": None,
        "seat_fee_table": None,
        "location": "서울 강남구 테헤란로 427",
        "coupon": {"name": "10% 할인 쿠폰", "discount_type": "RATE", "discount_value": Decimal("10.00")},
        "menus": [
            {"name": "제육볶음",   "category": "MENU",  "price": 10000, "stock": 30, "description": "제육볶음"},
            {"name": "김치찌개",   "category": "MENU",  "price": 9000,  "stock": 50, "description": "김치찌개"},
            {"name": "된장찌개",   "category": "MENU",  "price": 8000,  "stock": 50, "description": "된장찌개"},
            {"name": "순두부찌개", "category": "MENU",  "price": 8500,  "stock": 40, "description": "순두부찌개"},
            {"name": "콜라",       "category": "DRINK", "price": 2000,  "stock": 100, "description": "콜라"},
            {"name": "사이다",     "category": "DRINK", "price": 2000,  "stock": 100, "description": "사이다"},
        ],
        "set_menu": {
            "name": "제육+콜라 세트",
            "price": 10000,
            "description": "찌개와 음료 묶음",
            "items": [0, 4],  # 김치찌개 + 콜라 (menus 인덱스)
        },
    },
    {
        "name": "멋진호랑이들",
        "table_count": 25,
        "bank": "신한은행",
        "seat_type": "PP",
        "seat_fee_person": 3000,
        "seat_fee_table": None,
        "location": "서울 마포구 홍익로 5길 20",
        "coupon": {"name": "2000원 할인 쿠폰", "discount_type": "AMOUNT", "discount_value": Decimal("2000.00")},
        "menus": [
            {"name": "로제파스타",  "category": "MENU",  "price": 15000, "stock": 30, "description": "로제파스타"},
            {"name": "크림파스타", "category": "MENU",  "price": 14000, "stock": 30, "description": "크림파스타"},
            {"name": "고르곤졸라 피자", "category": "MENU",  "price": 18000, "stock": 20, "description": "고르곤졸라 피자"},
            {"name": "감자튀김", "category": "MENU",  "price": 10000, "stock": 40, "description": "감자튀김"},
            {"name": "레모네이드", "category": "DRINK", "price": 4000,  "stock": 80, "description": "레모네이드"},
            {"name": "아이스티",   "category": "DRINK", "price": 3500,  "stock": 80, "description": "아이스티"},
        ],
        "set_menu": {
            "name": "파스타+음료 세트",
            "price": 17000,
            "description": "파스타와 음료 묶음",
            "items": [0, 4],  # 로제파스타 + 레모네이드
        },
    },
    {
        "name": "멋스러운사자들",
        "table_count": 50,
        "bank": "카카오뱅크",
        "seat_type": "PT",
        "seat_fee_person": None,
        "seat_fee_table": 5000,
        "location": "서울 송파구 올림픽로 300",
        "coupon": {"name": "5% 할인 쿠폰", "discount_type": "RATE", "discount_value": Decimal("5.00")},
        "menus": [
            {"name": "짜장면",  "category": "MENU",  "price": 7000,  "stock": 60, "description": "짜장면"},
            {"name": "짬뽕",    "category": "MENU",  "price": 8000,  "stock": 60, "description": "짬뽕"},
            {"name": "탕수육",  "category": "MENU",  "price": 18000, "stock": 25, "description": "탕수육"},
            {"name": "볶음밥",  "category": "MENU",  "price": 8000,  "stock": 50, "description": "볶음밥"},
            {"name": "토닉",  "category": "DRINK", "price": 3000,  "stock": 100, "description": "토닉"},
            {"name": "레몬음료",    "category": "DRINK", "price": 4000,  "stock": 80, "description": "레몬음료"},
        ],
        "set_menu": {
            "name": "짜장+탕수육 세트",
            "price": 23000,
            "description": "짜장면과 탕수육 묶음",
            "items": [0, 2],  # 짜장면 + 탕수육
        },
    },
]

# 테이블 상태 분포 (AVAILABLE: 50%, IN_USE: 35%, INACTIVE: 15%)
TABLE_STATUS_WEIGHTS = [50, 50, 0]
TABLE_STATUSES = ["AVAILABLE", "IN_USE", "INACTIVE"]

RANDOM_SEED = 42  # 재현 가능한 랜덤


class Command(BaseCommand):
    help = "테스트 데이터 생성 (User 3개 기반)"

    def add_arguments(self, parser):
        parser.add_argument(
            "--reset",
            action="store_true",
            help="기존 시드 데이터를 삭제하고 재생성",
        )

    def handle(self, *args, **options):
        if options["reset"]:
            self._reset_data()

        self._create_users()

        users = User.objects.filter(username__in=["test1", "test2", "test3"]).order_by("username")


        rng = random.Random(RANDOM_SEED)

        self.stdout.write(f"User {users.count()}개 발견. 데이터 생성 시작...\n")

        with transaction.atomic():
            for i, (user, cfg) in enumerate(zip(users, BOOTH_CONFIGS)):
                self._seed_for_user(user, cfg, rng)

        self.stdout.write(self.style.SUCCESS("\n✅ 테스트 데이터 생성 완료!"))

    # ──────────────────────────────────────────
    # Users
    # ──────────────────────────────────────────
    def _create_users(self):
        for username in ["test1", "test2", "test3"]:
            if not User.objects.filter(username=username).exists():
                User.objects.create_user(username=username, password="test")
                self.stdout.write(f"    User 생성: {username}")
            else:
                self.stdout.write(f"    User 이미 존재: {username}")

    # ──────────────────────────────────────────
    # Reset
    # ──────────────────────────────────────────
    def _reset_data(self):
        from order.models import OrderItem, Order
        from cart.models import CartItem, Cart
        from coupon.models import CartCouponApply, CouponCode, TableCoupon, Coupon
        from table.models import TableUsage, Table, TableGroup
        from menu.models import SetMenuItem, SetMenu, Menu
        from booth.models import Booth

        self.stdout.write("기존 데이터 삭제 중...")
        for model in [OrderItem, Order, CartCouponApply, CartItem, Cart,
                      TableCoupon, CouponCode, Coupon, TableUsage,
                      Table, TableGroup, SetMenuItem, SetMenu, Menu, Booth]:
            model.objects.all().delete()
        User.objects.filter(username__in=["test1", "test2", "test3"]).delete()
        self.stdout.write(self.style.WARNING("기존 데이터 삭제 완료.\n"))

    # ──────────────────────────────────────────
    # User → 전체 플로우
    # ──────────────────────────────────────────
    def _seed_for_user(self, user: User, cfg: dict, rng: random.Random):
        name = cfg["name"]
        self.stdout.write(f"  [{user.username}] 부스: {name} (테이블 {cfg['table_count']}개)")

        booth  = self._create_booth(user, cfg)
        menus  = self._create_menus(booth, cfg)
        set_menu = self._create_set_menu(booth, cfg, menus)
        tables = self._create_tables(booth, cfg["table_count"], rng)
        coupon = self._create_coupon(booth, cfg)
        coupon_codes = self._create_coupon_codes(coupon, count=10)

        code_iter = iter(coupon_codes)

        in_use_count = available_with_history_count = 0
        for table in tables:
            if table.status == "IN_USE":
                code = next(code_iter, None)
                self._seed_active_session(booth, table, menus, set_menu, coupon, code)
                in_use_count += 1
            elif table.status == "AVAILABLE" and rng.random() < 0.4:
                # AVAILABLE 중 40%는 이전 세션 기록 보유
                self._seed_completed_session(table, menus, set_menu)
                available_with_history_count += 1
            # INACTIVE 및 나머지 AVAILABLE → 사용 기록 없음

        self.stdout.write(
            f"    IN_USE: {in_use_count}  |  완료 세션: {available_with_history_count}  |  빈 테이블: {cfg['table_count'] - in_use_count - available_with_history_count}"
        )
        self.stdout.write(f"  [{user.username}] ✓\n")

    # ──────────────────────────────────────────
    # Booth
    # ──────────────────────────────────────────
    def _create_booth(self, user: User, cfg: dict):
        from booth.models import Booth

        if Booth.objects.filter(user=user).exists():
            booth = Booth.objects.get(user=user)
            self.stdout.write("    → Booth 이미 존재. 건너뜀.")
            return booth

        booth = Booth(
            user=user,
            name=cfg["name"],
            account="110-123-456789",
            depositor=user.username,
            bank=cfg["bank"],
            table_max_cnt=cfg["table_count"],
            table_limit_hours=Decimal("2.00"),
            seat_type=cfg["seat_type"],
            seat_fee_person=cfg["seat_fee_person"],
            seat_fee_table=cfg["seat_fee_table"],
            operate_dates={
                "mon": True, "tue": True, "wed": True,
                "thu": True, "fri": True, "sat": True, "sun": False,
            },
            host_name=f"{cfg['name']} 운영팀",
            total_revenues=0,
            location=cfg["location"],
        )
        booth.save()  # QR 자동 생성
        return booth

    # ──────────────────────────────────────────
    # Menu
    # ──────────────────────────────────────────
    def _create_menus(self, booth, cfg: dict):
        from menu.models import Menu

        menus = []
        for d in cfg["menus"]:
            menu, _ = Menu.objects.get_or_create(
                booth=booth,
                name=d["name"],
                defaults={
                    "category": d["category"],
                    "price": Decimal(str(d["price"])),
                    "stock": d["stock"],
                    "description": d["description"],
                },
            )
            menus.append(menu)
        return menus

    def _create_set_menu(self, booth, cfg: dict, menus: list):
        from menu.models import SetMenu, SetMenuItem

        scfg = cfg["set_menu"]
        set_menu, created = SetMenu.objects.get_or_create(
            booth=booth,
            name=scfg["name"],
            defaults={"price": scfg["price"], "description": scfg["description"]},
        )
        if created:
            for idx in scfg["items"]:
                SetMenuItem.objects.create(set_menu=set_menu, menu=menus[idx], quantity=1)
        return set_menu

    # ──────────────────────────────────────────
    # Tables (랜덤 상태 부여)
    # ──────────────────────────────────────────
    def _create_tables(self, booth, count: int, rng: random.Random):
        from table.models import Table

        statuses = rng.choices(TABLE_STATUSES, weights=TABLE_STATUS_WEIGHTS, k=count)
        tables = []
        for num, status in enumerate(statuses, start=1):
            table, created = Table.objects.get_or_create(
                booth=booth,
                table_num=num,
                defaults={"status": status},
            )
            if not created and table.status != status:
                table.status = status
                table.save(update_fields=["status"])
            tables.append(table)
        return tables

    # ──────────────────────────────────────────
    # Coupon
    # ──────────────────────────────────────────
    def _create_coupon(self, booth, cfg: dict):
        from coupon.models import Coupon

        c = cfg["coupon"]
        coupon, _ = Coupon.objects.get_or_create(
            booth=booth,
            name=c["name"],
            defaults={
                "discount_type": c["discount_type"],
                "discount_value": c["discount_value"],
                "quantity": 30,
            },
        )
        return coupon

    def _create_coupon_codes(self, coupon, count: int):
        from coupon.models import CouponCode

        codes = []
        for i in range(count):
            code_str = f"C{coupon.booth_id:03d}{coupon.id:03d}{i:04d}"[:16]
            code, _ = CouponCode.objects.get_or_create(coupon=coupon, code=code_str)
            codes.append(code)
        return codes

    # ──────────────────────────────────────────
    # 활성 세션 (IN_USE 테이블)
    # ──────────────────────────────────────────
    def _seed_active_session(self, booth, table, menus, set_menu, coupon, coupon_code):
        from table.models import TableUsage
        from cart.models import Cart, CartItem
        from coupon.models import TableCoupon, CartCouponApply
        from order.models import Order, OrderItem

        started_at = timezone.now() - timezone.timedelta(hours=1)
        usage, _ = TableUsage.objects.get_or_create(
            table=table,
            ended_at=None,
            defaults={"started_at": started_at, "accumulated_amount": 0},
        )

        TableCoupon.objects.get_or_create(
            table_usage=usage,
            defaults={"coupon": coupon, "used_at": None},
        )

        # 메뉴 0번(메인)과 4번(음료) 사용
        main_menu  = menus[0]
        drink_menu = menus[4]
        main_price = int(main_menu.price)
        drink_price = int(drink_menu.price)
        cart_total = main_price * 2 + drink_price

        cart, _ = Cart.objects.get_or_create(
            table_usage=usage,
            defaults={
                "status": Cart.Status.ORDERED,
                "cart_price": cart_total,
                "round": 1,
            },
        )

        CartItem.objects.get_or_create(
            cart=cart, menu=main_menu,
            defaults={"quantity": 2, "price_at_cart": main_price},
        )
        CartItem.objects.get_or_create(
            cart=cart, setmenu=set_menu,
            defaults={"quantity": 1, "price_at_cart": int(set_menu.price)},
        )

        # 쿠폰 적용
        if coupon_code and not coupon_code.used_at:
            CartCouponApply.objects.get_or_create(
                cart=cart, round=1,
                defaults={"coupon_code": coupon_code},
            )
            coupon_code.mark_used()

        # 할인 계산 (RATE: %, AMOUNT: 원)
        original = main_price * 2 + int(set_menu.price)
        if coupon.discount_type == "RATE":
            discount = int(original * coupon.discount_value / 100)
        else:
            discount = int(coupon.discount_value)
        paid = original - discount

        order, created = Order.objects.get_or_create(
            event_id=uuid.uuid5(uuid.NAMESPACE_DNS, f"active-{usage.id}"),
            defaults={
                "table_usage": usage,
                "cart": cart,
                "order_price": paid,
                "original_price": original,
                "total_discount": discount,
                "coupon_id": coupon.id if coupon_code and coupon_code.used_at else None,
                "order_status": "PAID",
            },
        )

        if created:
            OrderItem.objects.create(
                order=order, menu=main_menu, quantity=2,
                fixed_price=main_price, status="served",
                cooked_at=timezone.now() - timezone.timedelta(minutes=30),
                served_at=timezone.now() - timezone.timedelta(minutes=25),
            )
            parent = OrderItem.objects.create(
                order=order, setmenu=set_menu, quantity=1,
                fixed_price=int(set_menu.price), status="served",
                cooked_at=timezone.now() - timezone.timedelta(minutes=28),
                served_at=timezone.now() - timezone.timedelta(minutes=20),
            )
            for menu_idx in set_menu.items.values_list("menu_id", flat=True):
                item_menu = next((m for m in menus if m.id == menu_idx), None)
                if item_menu:
                    OrderItem.objects.create(
                        order=order, menu=item_menu, parent=parent,
                        quantity=1, fixed_price=int(item_menu.price), status="served",
                    )

        usage.accumulated_amount = paid
        usage.save(update_fields=["accumulated_amount"])
        booth.total_revenues += paid
        booth.save(update_fields=["total_revenues"])

    # ──────────────────────────────────────────
    # 완료 세션 (AVAILABLE 테이블 일부)
    # ──────────────────────────────────────────
    def _seed_completed_session(self, table, menus, set_menu):
        from table.models import TableUsage
        from cart.models import Cart, CartItem
        from order.models import Order, OrderItem

        started_at = timezone.now() - timezone.timedelta(hours=3)
        ended_at   = timezone.now() - timezone.timedelta(hours=1)

        usage, _ = TableUsage.objects.get_or_create(
            table=table,
            ended_at=ended_at,
            defaults={
                "started_at": started_at,
                "ended_at": ended_at,
                "usage_minutes": 120,
                "accumulated_amount": 0,
            },
        )

        # 메뉴 1번(서브 메인)과 5번(음료2) 사용
        main_menu  = menus[1]
        drink_menu = menus[5]
        main_price  = int(main_menu.price)
        drink_price = int(drink_menu.price)
        total = main_price * 2 + drink_price * 2

        cart, _ = Cart.objects.get_or_create(
            table_usage=usage,
            defaults={
                "status": Cart.Status.ORDERED,
                "cart_price": total,
                "round": 1,
            },
        )

        CartItem.objects.get_or_create(
            cart=cart, menu=main_menu,
            defaults={"quantity": 2, "price_at_cart": main_price},
        )
        CartItem.objects.get_or_create(
            cart=cart, menu=drink_menu,
            defaults={"quantity": 2, "price_at_cart": drink_price},
        )

        order, created = Order.objects.get_or_create(
            event_id=uuid.uuid5(uuid.NAMESPACE_DNS, f"completed-{usage.id}"),
            defaults={
                "table_usage": usage,
                "cart": cart,
                "order_price": total,
                "original_price": total,
                "total_discount": 0,
                "order_status": "COMPLETED",
            },
        )

        if created:
            OrderItem.objects.create(
                order=order, menu=main_menu, quantity=2,
                fixed_price=main_price, status="served",
                cooked_at=ended_at - timezone.timedelta(minutes=60),
                served_at=ended_at - timezone.timedelta(minutes=55),
            )
            OrderItem.objects.create(
                order=order, menu=drink_menu, quantity=2,
                fixed_price=drink_price, status="served",
                cooked_at=ended_at - timezone.timedelta(minutes=60),
                served_at=ended_at - timezone.timedelta(minutes=58),
            )

        usage.accumulated_amount = total
        usage.save(update_fields=["accumulated_amount"])
