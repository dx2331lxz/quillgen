#!/bin/bash

# 获取第一个参数并且保存为端口
PORT=$1
# 如果没有参数，则使用默认端口
if [ -z "$PORT" ]; then
  echo "Usage: ./control.sh [port]"
  echo "Example: ./control.sh 8000"
  exit 1
fi
  # 确保端口是数字
if ! echo "$PORT" | grep -q '^[0-9]\+$'; then
  echo "Port must be a number"
  exit 1
fi
# 确保端口在1024到65535之间
if [ "$PORT" -lt 1024 ] || [ "$PORT" -gt 65535 ]; then
  echo "Port must be between 1024 and 65535"
  exit 1
fi

# 检查是否有进程占用port端口，并尝试杀死它
PID=$(sudo lsof -i:$PORT | grep LISTEN | awk '{print $2}' | tail -n 1)

if [ -n "$PID" ]; then
    echo "Killing process with PID $PID"
    sudo kill -9 "$PID"
fi

echo "Starting server on port $PORT"
/usr/local/bin/python3 /www/data/manage.py runserver 0.0.0.0:$PORT

#sleep 5
# 启动新的celery worker,--detach
# shellcheck disable=SC2046
#kill -TERM $(cat ./worker.pid)
#echo "Starting celery worker"
#/usr/local/bin/celery -A Editor.celery worker --loglevel=info --pidfile=worker.pid --logfile=./logs/worker.log

#tail -f /dev/null