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

    def __str__(self):
        return f"부스 {self.representative_table.booth.name} - 대표 테이블 : {self.representative_table.table_num}  / 병합된 테이블: {[table.table_num for table in self.tables.all()]} / 병합 시간: {self.merged_at}"

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
        unique_together = [['booth', 'table_num']]  # 같은 부스 내 번호 중복 방지

    def __str__(self):
        return f"부스 {self.booth.name} - 테이블 {self.table_num} {self.status}"
    
class TableUsage(models.Model):
    id = models.AutoField(primary_key=True)
    table = models.ForeignKey(Table, on_delete=models.CASCADE, related_name='usages')
    started_at = models.DateTimeField()
    ended_at = models.DateTimeField(null=True, blank=True)
    usage_minutes = models.IntegerField(null=True, blank=True)
        
    def __str__(self):
        return f"테이블 {self.table.table_num} 사용 기록: {self.started_at} - {self.ended_at} / 사용 시간(분): {self.usage_minutes}"
    
