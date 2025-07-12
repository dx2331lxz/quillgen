from datetime import datetime, timedelta
from itertools import count
from time import sleep

import requests
from django.contrib.auth.models import User
from django.http import HttpResponse

from . import models
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status, pagination  # 状态和分页
from rest_framework.parsers import MultiPartParser, JSONParser  # 文件上传`MultiPartParser`解析器
import json
import os
from Editor import settings
from . import serializer
from rest_framework.permissions import AllowAny
from rest_framework.decorators import api_view, permission_classes
# 引入日志
import logging
# 引入task
from . import tasks
from file import models as file_models

logger = logging.getLogger(__name__)

# 定义任务状态对应的分数
# ('pending', '待处理'),
# ('ongoing', '处理中'),
# ('failed', '失败'),
# ('prime', '等待中'),
# ('done', '已完成')
TASK_STATUS = {
    "pending": 0,
    "ongoing": 1,
    "failed": 0,
    "prime": 0,
    "done": 2
}
# 定义任务状态对应的中文
TASK_STATUS_CN = {
    "pending": "待处理",
    "ongoing": "处理中",
    "failed": "失败",
    "prime": "待编辑",
    "done": "已完成"
}


class TaskLogic(APIView):
    # permission_classes = (AllowAny,)
    def get(self, request):
        # 获取任务列表
        task_id = request.query_params.get("task_id")
        try:
            uid = request.user.id
        except User.DoesNotExist:
            logger.error("用户不存在")
            return Response("用户不存在", status=status.HTTP_401_UNAUTHORIZED)
        if task_id is None or task_id == "":
            tasks = models.Task.objects.filter(uid=uid).order_by("-created_at")
            serializers = serializer.TaskDetailSerializer(tasks, many=True)
        else:
            task = models.Task.objects.get(uid=uid, task_id=task_id)
            serializers = serializer.TaskSerializer(task)
        return Response(serializers.data, status=status.HTTP_200_OK)

    def post(self, request):
        try:
            uid = request.user.id
        except User.DoesNotExist:
            logger.error("用户不存在")
            return Response("用户不存在", status=status.HTTP_401_UNAUTHORIZED)
        data = request.data
        data['uid'] = uid
        content = data.get("content")
        try:
            data['content'] = json.dumps(data["content"])
        except Exception as e:
            logger.error(e.__str__())
            return Response({"error": e.__str__()}, status=status.HTTP_400_BAD_REQUEST)
        serializers = serializer.TaskSerializer(data=data)
        if serializers.is_valid():
            instance = serializers.save()
            self.publish(uid=uid, task_id=instance.task_id, content=content)
            serializers = serializer.TaskSerializer(models.Task.objects.get(uid=uid, task_id=instance.task_id))
            return Response(serializers.data, status=status.HTTP_201_CREATED)
        else:
            logger.error(serializers.errors)
            return Response(serializers.errors, status=status.HTTP_400_BAD_REQUEST)

    def put(self, request):
        data = request.data
        task_id = data.get("task_id")
        if task_id is None:
            logger.warning("task_id is None")
            return Response("task_id is None", status=status.HTTP_401_UNAUTHORIZED)
        try:
            uid = request.user.id
            if models.Task.objects.filter(uid=uid, task_id=task_id).exists():
                task = models.Task.objects.get(uid=uid, task_id=task_id)
            else:
                logger.warning("修改失败，任务不存在")
                return Response({"msg": "修改失败，任务不存在"}, status=status.HTTP_400_BAD_REQUEST)
        except User.DoesNotExist:
            logger.error("用户不存在")
            return Response("用户不存在", status=status.HTTP_401_UNAUTHORIZED)
        data = request.data
        if data.get("title"):
            task.title = data["title"]
            task.save()
        if data.get("content"):
            try:
                task.content = json.dumps(data["content"])
                task.save()
                self.publish(uid=uid, task_id=task.task_id, content=data["content"], update=True)
            except Exception as e:
                logger.error(e.__str__())
                return Response({"error": e.__str__()}, status=status.HTTP_400_BAD_REQUEST)
        return Response({"msg": "修改成功"}, status=status.HTTP_201_CREATED)

    def delete(self, request):
        data = request.data
        task_id = data.get("task_id")
        if task_id is None:
            logger.warning("task_id is None")
            return Response("task_id is None", status=status.HTTP_401_UNAUTHORIZED)
        try:
            uid = request.user.id
            if models.Task.objects.filter(uid=uid, task_id=task_id).exists():
                deleted, _ = models.Task.objects.filter(uid=uid, task_id=task_id).delete()
                if not deleted:
                    logger.error("删除失败")
                    return Response({"msg": "删除失败"}, status=status.HTTP_400_BAD_REQUEST)
                self.delete_task_items(uid=uid, task_id=task_id, task_item_ids=[])
                return Response({"msg": "删除成功"}, status=status.HTTP_200_OK)
            else:
                return Response({"msg": "删除失败"}, status=status.HTTP_400_BAD_REQUEST)
        except User.DoesNotExist:
            logger.error("用户不存在")
            return Response("用户不存在", status=status.HTTP_401_UNAUTHORIZED)

    def publish(self, uid, task_id, content, update=False):
        if content is None:
            logger.warning("content is None")
            return {}
        # post
        if not update:
            try:
                score = 0
                task_item_ids = []
                timeline_list = content.get("timeline")
                for timeline in timeline_list:
                    task_time = timeline.get("time")
                    task_list = timeline.get("task")
                    if task_list is None:
                        logger.warning("task is None")
                        continue
                    for task in task_list:
                        task_item_ids.append(task['id'])
                        score += TASK_STATUS.get(task['status'], 0)
                        self.create_task_items(uid=uid, task_id=task_id, task_item_id=task['id'], task_time=task_time,
                                               task_item=task)

                        logger.info("task_id: %s, task_item_id: %s, task_time: %s" % (task_id, task['id'], task_time))
                self.change_status(uid=uid, task_id=task_id, score=score, task_item_num=len(task_item_ids))
                return {"msg": "发布成功"}
            except Exception as e:
                logger.error(e.__str__())
                raise Exception("发布消息错误")
        # put
        else:
            try:
                score = 0
                task_item_ids = []
                timeline_list = content.get("timeline")
                for timeline in timeline_list:
                    task_time = timeline.get("time")
                    task_list = timeline.get("task")
                    if task_list is None:
                        logger.warning("task is None")
                        continue
                    for task in task_list:
                        task_item_ids.append(task['id'])
                        score += TASK_STATUS.get(task['status'], 0)
                        self.put_task_items(uid=uid, task_id=task_id, task_item_id=task['id'], task_time=task_time,
                                            task_item=task)
                        logger.info("task_id: %s, task_item_id: %s, task_time: %s" % (task_id, task['id'], task_time))
                self.delete_task_items(uid=uid, task_id=task_id, task_item_ids=task_item_ids)
                self.change_status(uid=uid, task_id=task_id, score=score, task_item_num=len(task_item_ids))

            except Exception as e:
                logger.error(e.__str__())
                raise Exception("发布消息错误")

    def create_task_items(self, uid, task_id, task_item_id, task_time, task_item):
        # 将task_time时间戳转换为datetime格式
        task_time = float(task_time) / 1000.0
        # 使用上海时间
        task_time = datetime.fromtimestamp(task_time)
        models.TaskItem.objects.create(uid=uid, task_id=task_id, task_item_id=task_item_id, title=task_item["title"],
                                       desc=task_item.get("desc", ""), status=task_item["status"],
                                       content=task_item.get("content", ""), start_time=task_time, end_time=task_time)

    def put_task_items(self, uid, task_id, task_item_id, task_time, task_item):
        # 将task_time时间戳转换为datetime格式

        task_time = float(task_time) / 1000.0
        # 使用上海时间
        task_time = datetime.fromtimestamp(task_time)
        models.TaskItem.objects.update_or_create(uid=uid, task_id=task_id, task_item_id=task_item_id,
                                                 defaults={
                                                     "title": task_item["title"],
                                                     "desc": task_item.get("desc", ""),
                                                     "status": task_item["status"],
                                                     "content": task_item.get("content", ""),
                                                     "start_time": task_time,
                                                     "end_time": task_time
                                                 })

    def delete_task_items(self, uid, task_id, task_item_ids):
        task_items = models.TaskItem.objects.filter(uid=uid, task_id=task_id)
        for task_item in task_items:
            logger.info(f"{task_item.task_item_id}")
            if task_item.task_item_id not in task_item_ids:
                task_item.delete()

    def change_status(self, uid, task_id, score, task_item_num):
        # score / task_item_num * 2 得到的小数保留整数部分
        logger.info(f"uid: {uid},task_id : {task_id}, score: {score}, task_item_num: {task_item_num}")
        if task_item_num == 0:
            return {"msg": "修改成功", "status": 0}
        change_num = int((score / (task_item_num * 2)) * 100)
        task = models.Task.objects.filter(uid=uid, task_id=task_id)
        if task:
            task.update(status=change_num)
            logger.info(f"修改任务状态成功：task_id: {task_id}, status: {change_num}")


# 获取今日代办任务
class TaskListView(APIView):
    def get(self, request):
        uid = request.user.id
        ## 根据今日时间获取任务
        # today_start, today_end = self.get_query_time_for_day()
        today = datetime.now().date()
        tasks = models.TaskItem.objects.filter(uid=uid, start_time__date=today)
        res = []
        for task in tasks:
            from_task = models.Task.objects.filter(task_id=task.task_id).first()
            task_title = '任务'
            if from_task:
                task_title = from_task.title
            foo = {
                "url": f"/timeline?id={task.task_id}&task={task.task_item_id}",
                "task_title": task_title,
                "task_item_title": task.title,
                "desc": task.desc,
                "status": task.status,
            }
            res.append(foo)

        return Response({"data": res}, status=status.HTTP_200_OK)


# 获取今日任务列表
def get_task_items_for_today(uid):
    today = datetime.now().date()
    tasks = models.TaskItem.objects.filter(start_time__date=today)
    res = []
    for task in tasks:
        foo = task.content
        res.append(foo)
    return res


def get_todo_task_items_for_today(uid):
    """
    获取今日待办任务列表
    :param uid:
    :return:
    """
    today = datetime.now().date()
    tasks = models.TaskItem.objects.filter(start_time__date=today)
    res = []
    for task in tasks:
        if task.status != "ongoing":
            continue
        foo = task.content
        res.append(foo)
    return res


def get_task_items_by_date(uid, date):
    """
    通过日期获取任务列表
    :param uid:
    :param date:
    :return:
    """
    # 将yyyy-mm-dd格式的字符串转换为datetime
    date = datetime.strptime(date, "%Y-%m-%d")
    tasks = models.TaskItem.objects.filter(uid=uid, start_time__date=date)
    res = []
    for task in tasks:
        from_task = models.Task.objects.filter(task_id=task.task_id).first()
        task_title = '任务'
        if from_task:
            task_title = from_task.title
        foo = {
            "task_id": task.task_id,
            "task_item_id": task.task_item_id,
            "task_title": task_title,
            "task_item_title": task.title,
            "desc": task.desc,
            "status": task.status,
        }
        res.append(foo)
    return res


# 获取本周任务列表
def get_task_items_for_week(uid):
    """
    获取本周任务列表
    :param uid:
    :return:
    """
    ## 获取今日所在的周的周一零点时间和周末零点时间
    week_start, week_end = get_current_week_boundaries()
    tasks = models.TaskItem.objects.filter(uid=uid, start_time__gte=week_start, end_time__lte=week_end)
    logger.info(f"{week_start}, {week_end}")
    logger.info(f"{tasks.count()}")
    foo = {}
    for task in tasks:
        if not foo.get(task.start_time.strftime("%Y-%m-%d")):
            foo[task.start_time.strftime("%Y-%m-%d")] = [task.content]
        else:
            foo[task.start_time.strftime("%Y-%m-%d")].append(task.content)
        logger.info(f"{task.start_time.strftime('%Y-%m-%d')}, {task.content}")

    return foo


# 获取本周工作项数量
def get_task_items_count(uid):
    """获取今日所在的周的周一零点时间和周末零点时间内的工作项数量"""
    week_start, week_end = get_current_week_boundaries()
    tasks = models.TaskItem.objects.filter(uid=uid, start_time__gte=week_start, end_time__lte=week_end)
    res_dict = {
        "pending": 0,
        "ongoing": 0,
        "failed": 0,
        "prime": 0,
        "done": 0
    }
    for task in tasks:
        res_dict[task.status] += 1
    return tasks.count(), res_dict


# 获取本周任务数量
def get_task_count(uid):
    """获取今日所在的周的周一零点时间和周末零点时间内的工作项数量
    TASK_STATUS = {
    "pending": 0,
    "ongoing": 1,
    "failed": 0,
    "prime": 0,
    "done": 2
}"""
    week_start, week_end = get_current_week_boundaries()
    tasks = models.Task.objects.filter(uid=uid, created_at__gte=week_start, created_at__lte=week_end)
    res_list = []
    for task in tasks:
        res_list.append(task.status)
    return tasks.count(), res_list


def get_current_week_boundaries():
    # 获取当前时间
    now = datetime.now()
    # 计算当前周的第一天（周一）
    # 如果现在是周一（isoweekday() == 1），则不需要调整
    # 否则，计算与当前周一相差的天数，并减去这些天数
    monday = now - timedelta(days=now.isoweekday() - 1)

    # 计算当前周的最后一天（周日）
    # 直接在周一的基础上加6天
    sunday = monday + timedelta(days=6)

    # 由于我们想要的是周日的23:59:59，所以加上一天的时间然后减去一秒
    sunday_end = sunday + timedelta(days=1) - timedelta(seconds=1)

    return monday.replace(hour=0, minute=0, second=0, microsecond=0), sunday_end.replace(hour=23, minute=59, second=59,
                                                                                         microsecond=0)


def get_all_texts(uid):
    """
    获取所有文本
    :param uid:
    :return:
    """
    texts = file_models.Text.objects.filter(user_id=uid)
    res = []
    for text in texts:
        foo = {
            "id": text.id,
            "content": text.content
        }
        res.append(foo)
    return res


def get_all_task_items(uid):
    """
    获取所有工作项
    :param uid:
    :return:
    """
    items = models.TaskItem.objects.filter(uid=uid)
    res = []
    for item in items:
        foo = {
            "id": item.task_item_id,
            "content": item.desc
        }
        res.append(foo)

    return res


## 修改工作项状态
class TaskItemStatusView(APIView):
    def post(self, request):
        try:
            uid = request.user.id
            task_item_id = request.data["task_item_id"]
            item_status = request.data["status"]
            task_item = models.TaskItem.objects.get(uid=uid, task_item_id=task_item_id)
            task_item.status = item_status
            task_item.save()
            task_id = task_item.task_id
            logger.info(f"task_id: {task_id}, task_item_id: {task_item_id}")
            self.change_item_status(task_id, task_item_id, item_status)
            return Response({"msg": "修改成功"}, status=status.HTTP_200_OK)
        except Exception as e:
            logger.error(e.__str__())
            return Response({"msg": "修改失败"}, status=status.HTTP_400_BAD_REQUEST)

    def change_item_status(self, task_id, task_item_id, item_status):
        task = models.Task.objects.filter(task_id=task_id)
        if task:
            task = task.first()
        else:
            logger.warning(f"task_id: {task_id} not found")
            return
        content = task.content
        logger.info(f"typecontent: {type(content)}")
        logger.info(f"content: {content}")
        score = 0
        item_num = 0
        if content:
            content = json.loads(content)
            timelines = content["timeline"]
            for timeline in timelines:
                tasks = timeline["task"]
                for t in tasks:
                    item_num += 1
                    if t["id"] == task_item_id:
                        t["status"] = item_status
                    score += TASK_STATUS.get(t["status"], 0)
        logger.info(f"update task: {task_id}, content: {content}")
        task.content = json.dumps(content)
        task_score = int((score / (item_num * 2)) * 100)
        logger.info(f"task_score: {task_score}, score: {score}, item_num: {item_num}")
        task.status = task_score
        task.save()


## 统计任务情况（数量，状态）
class TaskStatisticView(APIView):
    def get(self, request):
        uid = request.user.id
        task_count, task_status_list = get_task_count(uid=uid)
        task_items_count, task_items_dict = get_task_items_count(uid=uid)
        return Response(
            {"task_count": task_count, "task_status_list": task_status_list, "task_items_count": task_items_count,
             "task_items_dict": task_items_dict},
            status=status.HTTP_200_OK)


# 异步任务demo: 删除工作项
# @permission_classes([AllowAny])
@api_view(['POST'])
def delete_items_by_taskid(request):
    data = request.data
    uid = request.user.id
    task_id = data.get("task_id")
    if not task_id or not uid:
        return Response({"msg": "参数错误"}, status=status.HTTP_400_BAD_REQUEST)

    task_item_list = models.TaskItem.objects.filter(uid=uid, task_id=task_id)
    if task_item_list.count() < 2:
        for task_item in task_item_list:
            task_item.delete()
        return Response({'msg': "删除成功"}, status=status.HTTP_200_OK)
    task_item_id_list = [i.task_item_id for i in task_item_list]
    # 如果大于等于2个，异步任务
    url = "http://81.70.143.162:7788/message/send/"
    body = {
        "msg_type": 0,
        "content": {
            "task_item_id_list": task_item_id_list,
            "uid": uid,
        }
    }
    response = requests.post(url, json=body)
    logger.info(response.json)
    return Response(response.json(), status=status.HTTP_200_OK)

@api_view(['POST'])
@permission_classes([AllowAny])
def delete_items_by_itemid(request):
    data = request.data
    uid = data.get("uid")
    item_id_list = data.get("task_item_id_list")
    if not item_id_list or not uid:
        return Response({"msg": "参数错误"}, status=status.HTTP_400_BAD_REQUEST)
    for item_id in item_id_list:
        models.TaskItem.objects.filter(uid=uid, task_item_id=item_id).delete()

    return Response({'msg': "删除成功"}, status=status.HTTP_200_OK)