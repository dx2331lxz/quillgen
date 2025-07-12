from . import models
from celery import shared_task
import logging

logger = logging.getLogger(__name__)

import time
from datetime import datetime, timezone, timedelta


# 创建
@shared_task(name="create_task_items")
def create_task_items(uid, task_id, task_item_id, task_time, task_item):
    # 将task_time时间戳转换为datetime格式
    task_time = float(task_time) / 1000.0
    # 使用上海时间
    task_time = datetime.fromtimestamp(task_time)
    models.TaskItem.objects.create(uid=uid, task_id=task_id, task_item_id=task_item_id, title=task_item["title"],
                                   desc=task_item.get("desc", ""), status=task_item["status"],
                                   content=task_item.get("content", ""), start_time=task_time, end_time=task_time)


@shared_task(name="put_task_items")
def put_task_items(uid, task_id, task_item_id, task_time, task_item):
    # 将task_time时间戳转换为datetime格式

    task_time = float(task_time) / 1000.0
    # 使用上海时间
    task_time = datetime.fromtimestamp(task_time)
    print(uid, task_id, task_item_id)
    print(f"type of uid: {type(uid)}, type of task_id: {type(task_id)}, type of task_item_id: {type(task_item_id)}")
    models.TaskItem.objects.filter(uid=uid, task_id=task_id, task_item_id=task_item_id).update(title=task_item["title"],
                                                                                               desc=task_item.get(
                                                                                                   "desc", ""),
                                                                                               status=task_item[
                                                                                                   "status"],
                                                                                               content=task_item.get(
                                                                                                   "content", ""),
                                                                                               start_time=task_time,
                                                                                               end_time=task_time)


@shared_task(name="delete_task_items")
def delete_task_items(uid, task_id, task_item_ids):
    logger.info(f"task_id: {task_id}, task_item_ids: {task_item_ids}")
    logger.info(f"type of task_id: {type(task_id)}, type of task_item_ids: {type(task_item_ids)}")
    task_items = models.TaskItem.objects.filter(uid=uid, task_id=task_id)
    for task_item in task_items:
        logger.info(f"112312312313: {task_item.task_item_id}")
        if task_item.task_item_id not in task_item_ids:
            task_item.delete()


@shared_task(name="change_task_status")
def change_status(uid, task_id, score, task_item_num):
    # score / task_item_num * 2 得到的小数保留整数部分
    if task_item_num == 0:
        return {"msg": "修改成功", "status": 0}
    change_num = int((score / (task_item_num * 2)) * 100)
    task = models.Task.objects.filter(uid=uid, task_id=task_id).first()
    if task:
        models.Task.objects.filter(uid=uid, task_id=task_id).update(status=change_num)
        logger.info("task_id: %s, status: %d" % (task_id, change_num))
