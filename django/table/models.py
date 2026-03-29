from django.db import models
from django.utils.timezone import now
# Create your models here.

class TableGroup(models.Model):
    """테이블 병합 그룹 모델"""
    id = models.AutoField(primary_key=True)
    representative_table = models.ForeignKey(
        'Table',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='representative_group'
    )
    merged_at = models.DateTimeField(default=now)

    class Meta:
        verbose_name = '테이블 그룹'
        verbose_name_plural = '테이블 그룹 목록'
        ordering = ['-merged_at']

    def __str__(self):
        if self.representative_table:
            return f"[그룹 {self.pk}] {self.representative_table.booth.name} - 대표 테이블 {self.representative_table.table_num}"
        return f"[그룹 {self.pk}] (대표 테이블 없음)"

class Table(models.Model):
    id = models.AutoField(primary_key=True)
    booth = models.ForeignKey('booth.Booth', on_delete=models.CASCADE, related_name='tables')
    table_num = models.IntegerField()

    class Status(models.TextChoices):
        ACTIVE = 'AVAILABLE', '활성화' # 사용자가 입장 할 수 있는 상태
        IN_USE = 'IN_USE', '사용중' # 사용자가 사용중인 상태
        INACTIVE = 'INACTIVE', '비활성화'

    status = models.CharField(max_length=20, choices=Status.choices, default=Status.ACTIVE)

    group = models.ForeignKey(
        TableGroup,  # ← 직접 참조 (위에 정의됨)
        on_delete=models.SET_NULL,
        related_name='tables',
        null=True,
        blank=True
    )
    class Meta:
        verbose_name = '테이블'
        verbose_name_plural = '테이블 목록'
        unique_together = [['booth', 'table_num']]
        ordering = ['booth', 'table_num']

    def __str__(self):
        return f"[{self.booth.name}] 테이블 {self.table_num} ({self.get_status_display()})"
    
class TableUsage(models.Model):
    id = models.AutoField(primary_key=True)
    table = models.ForeignKey(Table, on_delete=models.CASCADE, related_name='usages')
    started_at = models.DateTimeField()
    ended_at = models.DateTimeField(null=True, blank=True)
    usage_minutes = models.IntegerField(null=True, blank=True)
    accumulated_amount = models.IntegerField(null=False,default=0) # 테이블 세션 누적 총액

    class Meta:
        verbose_name = '테이블 사용 기록'
        verbose_name_plural = '테이블 사용 기록 목록'
        ordering = ['-started_at']

    def __str__(self):
        status = '사용중' if self.ended_at is None else f"{self.usage_minutes}분 사용"
        return f"[{self.table.booth.name}] 테이블 {self.table.table_num} - {self.started_at:%Y-%m-%d %H:%M} ({status}, {self.accumulated_amount:,}원)"
    
