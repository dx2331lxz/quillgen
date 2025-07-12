FROM python:3.9

#设置虚拟环境变量
ENV PYTHONUNBUFFERED 1

# 在容器的指定目录下面创建项目的文件夹
RUN mkdir -p  /www/data
#设置容器的工作目录（也就是当前的 django 的位置）
#WORKDIR /usr/django/app
WORKDIR /www/data
#COPY requirements.txt.txt /www/data
COPY . .
#使用 pip 安装依赖

RUN pip install -r requirements.txt

#CMD ["sh", "-c", "python manage.py runserver 0.0.0.0:8000"]
# 授予当前目录下的control.sh执行权限，并且执行./control.sh 8000
RUN chmod +x control.sh

CMD ["./control.sh", "8000"]