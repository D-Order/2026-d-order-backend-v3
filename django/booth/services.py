from booth.models import Booth
from menu.models import Menu

class BoothService:

    @staticmethod
    def create_booth_for_user(user, booth_data):
        """유저 생성 시 부스 데이터 만드는 함수
        Args:
            user (User): 유저 객체
            booth_data (dict): 부스 데이터
        Returns:
            생성한 Booth 객체
        """
        from table.models import Table

        # 3. Booth 객체 생성
        booth = Booth.objects.create(
            user=user,
            name=booth_data['name'],
            account=booth_data['account'],
            depositor=booth_data['depositor'],
            bank=booth_data['bank'],
            table_max_cnt=booth_data['table_max_cnt'],
            table_limit_hours=booth_data['table_limit_hours'],
            seat_type=booth_data['seat_type'],
            seat_fee_person=booth_data.get('seat_fee_person'),
            seat_fee_table=booth_data.get('seat_fee_table'),
        )

        # 4. 테이블 이용료 메뉴 자동 생성
        if booth.seat_type == "PP":
            Menu.objects.create(
                booth=booth,
                name="테이블 이용료",
                category="FEE",
                description="인원 수",
                price=booth.seat_fee_person or 0,
                stock=9999
            )
        elif booth.seat_type == "PT":
            Menu.objects.create(
                booth=booth,
                name="테이블 이용료",
                category="FEE",
                description="테이블",
                price=booth.seat_fee_table or 0,
                stock=9999
            )
        else:
            Menu.objects.create(
                booth=booth,
                name="테이블 이용료",
                category="FEE",
                description="FREE",
                price=0,
                stock=9999
            )

        # 테이블 생성
        for i in range(1, booth.table_max_cnt + 1):
            Table.objects.create(
                booth=booth,
                table_num=i
            )
        return booth

    @staticmethod
    def update_booth(booth, booth_data):
        """부스 마이페이지 데이터 업데이트 및 FEE 메뉴 동기화
        Args:
            booth_data (dict): 변경할 부스 데이터
        """
        # 기존 값 변경
        for key, value in booth_data.items():
            setattr(booth, key, value)
        booth.save()

        # FEE 메뉴 동기화
        fee_menu = Menu.objects.filter(booth=booth, category="FEE").first()
        if fee_menu:
            if booth.seat_type == "PP":
                fee_menu.price = booth.seat_fee_person or 0
                fee_menu.description = "인원 수"
            elif booth.seat_type == "PT":
                fee_menu.price = booth.seat_fee_table or 0
                fee_menu.description = "테이블"
            else:
                fee_menu.price = 0
                fee_menu.description = "FREE"
            fee_menu.save()


