> 源项目地址：https://daoxuan.coding.net/p/editor/d/Editor/git，由于coding的更新策略迁移至此
# 项目名称

## 简介

本项目为ai编辑器的后端部分，使用Django框架开发。

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

## 配置文件设置

在开始使用之前，请按照以下步骤设置配置文件：

1. 复制 `config.ini.example` 文件并重命名为 `config.ini`：
   ```bash
   cp config.ini.example config.ini
   ```

2. 编辑 `config.ini` 文件，填入您的实际配置值：
   - COZE API 配置
   - 阿里云 OSS 配置
   - 百度 API 配置
   - SMS 服务配置
   - DeepSeek API 配置
   - SILICONFLOW API 配置

⚠️ **重要提醒**: `config.ini` 文件包含敏感信息，已被添加到 `.gitignore` 中，不会被提交到版本控制。请妥善保管您的配置文件。

## 邮箱验证
由于SMTP.starttls() got an unexpected keyword argument 'keyfile'报错的原因，python 3.12及以上暂时无法使用邮箱验证功能。
请保证python环境小于3.12
