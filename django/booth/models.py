from django.db import models
from django.contrib.auth.models import User
from django.core.validators import MinValueValidator, MaxValueValidator


# For QR
import qrcode
from django.conf import settings
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
    table_max_cnt = models.IntegerField(validators=[MinValueValidator(0), MaxValueValidator(200)])
    table_limit_hours = models.DecimalField(max_digits=4, decimal_places=2)

    # 요금 정보
    class SEAT_TYPE(models.TextChoices):
        NO = 'NO', 'No Seat Fee'
        PP = 'PP', 'Seat Fee Per Person'
        PT = 'PT', 'Seat Fee Per Table'

    seat_type = models.CharField(max_length=2, choices=SEAT_TYPE.choices, default='NO')
    seat_fee_person = models.IntegerField(null=True, blank=True)
    seat_fee_table = models.IntegerField(null=True, blank=True)

    # 운영 정보
    operate_dates = models.JSONField(default=dict)
    host_name = models.CharField(max_length=100, blank=True, null=True, help_text="주최 이름")
    total_revenues = models.IntegerField(default=0)
    location = models.CharField(max_length=200, blank=True, null=True, help_text="부스 위치")

    qr_image = models.ImageField(upload_to='qr_images/', blank=True, null=True, help_text='부스 전용 QR 코드 이미지')
    thumbnail_image = models.ImageField(upload_to='thumbnails/', blank=True, null=True, help_text='부스 썸네일 이미지')

    class Meta:
        verbose_name = '부스'
        verbose_name_plural = '부스 목록'
        ordering = ['pk']
    def generate_qr(self):

        # 기존 QR 이미지가 있으면 삭제
        if self.qr_image:
            self.qr_image.delete(save=False)

        
        qr_data = f"https://{settings.CUSTOMER_FRONT_BASE_URL}/?id={self.pk}"  
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
            super().save(update_fields=["qr_image"])

    def __str__(self):
        return f"{self.pk} - {self.name}"