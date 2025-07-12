from django.urls import path
from . import views

urlpatterns = [
    path('manage/', views.TaskLogic.as_view(), name='task_manage'),
    path('list_today/', views.TaskListView.as_view(), name='task_list'),
    path('taskitemstatus/', views.TaskItemStatusView.as_view(), name='task_status'),
#     获取任务数量
    path('statistic/', views.TaskStatisticView.as_view(), name='task_number'),
    path('task_item/delete_by_taskid/', views.delete_items_by_taskid, name='task_item_delete'),
    path('task_item/delete_by_task_item_id/', views.delete_items_by_itemid, name='task_item'),
]