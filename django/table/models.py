from django.db import models
from django.utils.timezone import now
# Create your models here.


class Table(models.Model):
    id = models.AutoField(primary_key=True)
    booth = models.ForeignKey('booth.Booth', on_delete=models.CASCADE, related_name='tables')
    table_num = models.IntegerField()
    
    class status(models.TextChoices):
        ACTIVE = 'AVAILABLE', '활성화' # 사용자가 입장 할 수 있는 상태
        IN_USE = 'IN_USE', '사용중' # 사용자가 사용중인 상태
        INACTIVE = 'INACTIVE', '비활성화' 
        

    status = models.CharField(max_length=20, choices=status.choices, default=status.ACTIVE)
    
    def reset_table(self):
        pass

    def __str__(self):
        return f"부스 {self.booth.name} - 테이블 {self.table_num} {self.status}"
    
class TableUsage(models.Model):
    id = models.AutoField(primary_key=True)
    table = models.ForeignKey(Table, on_delete=models.CASCADE, related_name='usages')
    started_at = models.DateTimeField()
    ended_at = models.DateTimeField(null=True, blank=True)
    usage_minutes = models.IntegerField(null=True, blank=True)
        
    def __str__(self):
        return f"테이블 {self.table.table_num} 사용 기록: {self.started_time} - {self.ended_time} / 사용 시간(분): {self.usage_minutes}"