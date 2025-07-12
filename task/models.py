import uuid

from django.db import models


# Create your models here.

class Task(models.Model):
    task_id = models.AutoField(primary_key=True)
    uid = models.IntegerField()
    title = models.CharField(max_length=100)
    status = models.IntegerField(default=0, editable=True)
    content = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True, auto_now=False)
    updated_at = models.DateTimeField(auto_now_add=False, auto_now=True)

    # 定义数据库名称
    def __str__(self):
        return self.title

    # 定义数据库名称
    class Meta:
        db_table = 'task'


class TaskItem(models.Model):
    # 任务项id使用uuid
    task_item_id = models.CharField(primary_key=True, default=uuid.uuid4, editable=True, max_length=100)
    task_id = models.IntegerField()
    uid = models.IntegerField()
    title = models.CharField(max_length=100)
    content = models.TextField(null=True, blank=True)
    status_list = [
        ('pending', '待处理'),
        ('ongoing', '处理中'),
        ('failed', '失败'),
        ('prime', '待编辑'),
        ('done', '已完成')
    ]
    status = models.CharField(choices=status_list, default=status_list[0][0], max_length=16)
    desc = models.CharField(max_length=256, null=True, blank=True)
    start_time = models.DateTimeField(null=True, blank=True)
    end_time = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, auto_now=False)
    updated_at = models.DateTimeField(auto_now_add=False, auto_now=True)

    # 定义数据库名称
    def __str__(self):
        return self.title

    # 定义数据库名称
    class Meta:
        db_table = 'task_item'
