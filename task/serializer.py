""" Serializer """
from rest_framework import serializers

from task.models import Task


class TaskSerializer(serializers.ModelSerializer):
    class Meta:
        model = Task
        fields = "__all__"

class TaskDetailSerializer(serializers.ModelSerializer):
    class Meta:
        model = Task
        exclude = ["content"]