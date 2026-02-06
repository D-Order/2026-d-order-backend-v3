from django.db import models
from django.contrib.auth.models import User


# For QR
import qrcode
from io import BytesIO
from django.core.files.base import ContentFile

# Create your models here.
class Booth(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, primary_key=True, related_name='booth') # user를 booth의 pk로 사용
    
    # 이름
    name = models.CharField(max_length=20)

    # 은행 정보
    account = models.CharField(max_length=50)
    depositor = models.CharField(max_length=50, default="Unknown")
    bank = models.CharField(max_length=50)

    # 테이블 정보
    table_max_cnt = models.IntegerField()
    table_limit_hours = models.DecimalField(max_digits=4, decimal_places=2)
    qr_image = models.ImageField(upload_to='qr_images/', blank=True, null=True, help_text='부스 전용 QR 코드 이미지')


    # 요금 정보
    SEAT_TYPE_CHOICES = [
        ('NO', 'No Seat Tax'),
        ('PP', 'Seat Tax Per Person'),
        ('PT', 'Seat Tax Per Table'),
    ]

    seat_type = models.CharField(max_length=2, choices=[("NO","없음"),("PP","1인당"),("PT","테이블당")])
    seat_tax_person = models.IntegerField(null=True, blank=True)
    seat_tax_table = models.IntegerField(null=True, blank=True)

    
    def generate_qr(self):

        qr_data = f"https://frontend-url.com/booth/{self.pk}/"  #TODO : 부스 고유 URL로 변경
        qr = qrcode.QRCode(version=1, box_size=10, border=5)
        qr.add_data(qr_data)
        qr.make(fit=True)

        img = qr.make_image(fill='black', back_color='white')
        buffer = BytesIO()
        img.save(buffer, format='PNG')
        file_name = f'booth_{self.pk}_qr.png'
        self.qr_image.save(file_name, ContentFile(buffer.getvalue()), save=False)

    # 최초 생성 시 이미지가 없으면 자동 생성
    def save(self, *args, **kwargs):
        is_new = self._state.adding
        super().save(*args, **kwargs)
        if is_new and not self.qr_image:
            self.generate_qr()
            super().save(update_fields=["table_qr_image"])