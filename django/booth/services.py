from booth.models import Booth

class BoothService:

    @staticmethod
    def create_booth_for_user(user, booth_data):
        """유저 생성 시 부스 데이트 만드는 함수

        Args:
            user (User): 유저 객체
            booth_data (dict): 부스 데이터

        Returns:
            생성한 Booth 객체
        """
        # from menu.models import Menu  # TODO: Menu 모델 구현 후 활성화
        # from table.models import Table  # TODO: Table 모델 구현 후 활성화

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

        # TODO: Menu 모델 확립 후 다시 구현
        # 이건 여기 두는게 나을 듯
        # 4. 테이블 이용료 메뉴 자동 생성
        # if booth.seat_type == "PP":
        #     Menu.objects.create(
        #         booth=booth,
        #         menu_name="테이블 이용료(1인당)",
        #         menu_description="좌석 이용 요금(1인 기준)",
        #         menu_category="seat_fee",
        #         menu_price=booth.seat_fee_person,
        #         menu_amount=999999  # 사실상 무제한
        #     )
        # elif booth.seat_type == "PT":
        #     Menu.objects.create(
        #         booth=booth,
        #         menu_name="테이블 이용료(테이블당)",
        #         menu_description="좌석 이용 요금(테이블 기준)",
        #         menu_category="seat_fee",
        #         menu_price=booth.seat_fee_table,
        #         menu_amount=999999
        #     )

        # TODO: Table 모델 작성 후 다시 구현
        # 이것도 여기 두는게 나을 듯
        # 5. 테이블 자동 생성
        # for i in range(1, booth.table_max_cnt + 1):
        #     Table.objects.create(
        #         booth=booth,
        #         table_num=i,
        #         status="out",
        #     )

        return booth
