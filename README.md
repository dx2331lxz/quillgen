# 项目名称

## 简介

简短介绍你的Django项目是做什么的，它的主要功能和目标用户是谁。

## 环境依赖


- Python >= 3.8

- Django >= 3.2

- 其他依赖（如数据库、外部API、第三方Python库等）

### 安装依赖

在项目根目录下，运行以下命令来安装所有Python依赖：

```bash
pip install -r requirements.txt
```

## 运行项目
### 赋予control.sh可执行权限
```bash
chmod +x control.sh
```
### 启动项目
```bash
./control.sh 8000
```
### 停止项目（未开发）
```bash
./control.sh stop
```
## 访问项目
当前使用云开发环境，访问 http://${主机ip}:${主机映射端口}/ 即可看到项目页面。
例如：http://81.70.143.162:8808/
