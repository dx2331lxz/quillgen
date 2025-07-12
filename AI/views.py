import logging
import queue
import threading
import time
import uuid
from datetime import datetime
from io import BytesIO

from django.shortcuts import render, HttpResponse
from django.http import StreamingHttpResponse, FileResponse
from rest_framework.parsers import MultiPartParser

from . import serializer, models
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status, pagination  # 状态和分页
import json
import re
import os
from file import models as file_models
# jwt
from rest_framework.permissions import AllowAny
from rest_framework.permissions import IsAuthenticated
from rest_framework_simplejwt.authentication import JWTAuthentication, JWTTokenUserAuthentication
from rest_framework_simplejwt.views import TokenObtainPairView
from rest_framework_simplejwt.tokens import RefreshToken
from openai import OpenAI
# coze
from utils.connect_coze import connect_coze

from task.views import get_task_items_for_today, get_task_items_for_week, get_todo_task_items_for_today, \
    get_task_items_by_date, get_all_texts, get_all_task_items

import erniebot
from Editor import settings
import base64
import pathlib
import pprint
import json
import requests

erniebot.api_type = 'aistudio'
erniebot.access_token = settings.ACCESS_TOKEN
# deepseek
deepseek_client = OpenAI(api_key=settings.DeepSeek_APIKEY, base_url=settings.DeepSeek_Chat_URL)
# 硅基流动
siliconflow_client = OpenAI(api_key=settings.SILICONFLOW_APIKEY, base_url=settings.SILICONFLOW_URL)

# Create your views here.
logger = logging.getLogger(__name__)
import base64


# 从字符串中提取最外围json
def get_json(s):
    pattern = r'\{.*\}'
    match = re.search(pattern, s)
    if match:
        data = json.loads(match.group())
        return data
    else:
        return None


class Translate(APIView):

    def post(self, request):
        data = request.data
        content = data.get('content')
        type = data.get('type')
        if not type:
            return Response({'msg': '请输入目标语言'}, status=status.HTTP_400_BAD_REQUEST)
        if not content:
            return Response({'msg': '请输入内容'}, status=status.HTTP_400_BAD_REQUEST)

        def event_generator():
            response_stream = siliconflow_client.chat.completions.create(
                model="THUDM/glm-4-9b-chat",
                messages=[
                    {"role": "user", "content": f"""请翻译下面的句子为{type}：{content}"""},
                ],
                stream=True,
            )
            while True:
                for chunk in response_stream:
                    if hasattr(chunk, 'choices'):
                        for choice in chunk.choices:
                            if hasattr(choice, 'delta') and hasattr(choice.delta, 'content'):
                                print(choice.delta.content, end='')
                                res = base64.b64encode(choice.delta.content.encode()).decode()
                                yield f'data: {res}\n\n'
                yield f'data: [DONE]\n\n'
                break

        response = StreamingHttpResponse(
            event_generator(),
            content_type='text/event-stream;charset=UTF-8',

        )
        response['Cache-Control'] = 'no-cache'
        return response


class Summary(APIView):

    def post(self, request):
        data = request.data
        content = data.get('content')
        if not content:
            return Response({'msg': '请输入内容'}, status=status.HTTP_400_BAD_REQUEST)
        model = data.get('model')
        if not model or model not in ['Pro/deepseek-ai/DeepSeek-V3']:
            model = "THUDM/glm-4-9b-chat"

        def event_generator():
            response_stream = siliconflow_client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "user", "content": f"""请你总结下面的文字：{content}"""},
                ],
                stream=True,
            )
            while True:
                for chunk in response_stream:
                    if hasattr(chunk, 'choices'):
                        for choice in chunk.choices:
                            if hasattr(choice, 'delta') and hasattr(choice.delta, 'content'):
                                print(choice.delta.content, end='')
                                res = base64.b64encode(choice.delta.content.encode()).decode()
                                yield f'data: {res}\n\n'
                yield f'data: [DONE]\n\n'
                break

        response = StreamingHttpResponse(
            event_generator(),
            content_type='text/event-stream;charset=UTF-8',

        )
        response['Cache-Control'] = 'no-cache'
        return response


class Abstract(APIView):

    def post(self, request):
        data = request.data
        content = data.get('content')
        model = data.get('model')
        if not model or model not in ['Pro/deepseek-ai/DeepSeek-V3']:
            model = "THUDM/glm-4-9b-chat"
        if not content:
            return Response({'msg': '请输入内容'}, status=status.HTTP_400_BAD_REQUEST)

        def event_generator():
            response_stream = siliconflow_client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "user", "content": f"""给出下面的文字的摘要: {content}"""},
                ],
                stream=True,
            )
            while True:
                for chunk in response_stream:
                    if hasattr(chunk, 'choices'):
                        for choice in chunk.choices:
                            if hasattr(choice, 'delta') and hasattr(choice.delta, 'content'):
                                print(choice.delta.content, end='')
                                res = base64.b64encode(choice.delta.content.encode()).decode()
                                yield f'data: {res}\n\n'
                yield f'data: [DONE]\n\n'
                break

        response = StreamingHttpResponse(
            event_generator(),
            content_type='text/event-stream;charset=UTF-8',

        )
        response['Cache-Control'] = 'no-cache'
        return response


class Continue2Write(APIView):

    def post(self, request):

        data = request.data
        content = data.get('content')
        goal = data.get('goal')
        model = data.get('model')
        if not model or model not in ['Pro/deepseek-ai/DeepSeek-V3']:
            model = "THUDM/glm-4-9b-chat"
        if not content:
            return Response({'msg': '请输入内容'}, status=status.HTTP_400_BAD_REQUEST)
        if goal:
            prompt = f"""请将"{content}"帮助我往{goal}方向续写。"""
        else:
            prompt = f"""请将下面的文字续写：{content}"""

        def event_generator():
            response_stream = siliconflow_client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "user", "content": prompt},
                ],
                stream=True,
            )
            while True:
                for chunk in response_stream:
                    if hasattr(chunk, 'choices'):
                        for choice in chunk.choices:
                            if hasattr(choice, 'delta') and hasattr(choice.delta, 'content'):
                                res = base64.b64encode(choice.delta.content.encode()).decode()
                                yield f'data: {res}\n\n'
                yield f'data: [DONE]\n\n'
                break

        response = StreamingHttpResponse(
            event_generator(),
            content_type='text/event-stream;charset=UTF-8',

        )
        response['Cache-Control'] = 'no-cache'
        return response


class Wrong2Right(APIView):
    def wrong2right(self, content, model):
        response = siliconflow_client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": """你是一个专业语法校对工具，请按以下规则处理输入文本：
        1. 仅修正语法错误，忽略拼写、用词不当等其他问题
        2. 输出格式为严格JSON：
        [
          {
            "Original": "原句内容",
            "Corrected": "修正后内容", 
            "ErrorType": "语法错误类型",
            "Reason": "修改依据说明"
          }
          // 多个错误按此格式追加
        ]
        3. 禁止任何格式外的文字说明
        4. 保持输出为合法JSON结构

        输入示例：
        "她昨天去学校了。他非常认真。我吃饭在七点。"

        输出示例：
        [
          {
            "Original": "我吃饭在七点",
            "Corrected": "我在七点吃饭",
            "ErrorType": "语序错误",
            "Reason": "时间状语位置不当，应置于动词前"
          }
        ]
        注意: 
        1. 如果没有错误，返回空列表[]
        2. Original部分一定要返回原句"""},
                {"role": "user", "content": content},
            ],
            response_format={"type": "json_object"},
        )
        return response.choices[0].message.content

    def post(self, request):
        # return Response(data_list, status=status.HTTP_200_OK)
        data = request.data
        content = data.get('content')
        if not content:
            return Response({'msg': '请输入内容'}, status=status.HTTP_400_BAD_REQUEST)
        model = data.get('model')
        if not model or model not in ['Pro/deepseek-ai/DeepSeek-V3']:
            model = "THUDM/glm-4-9b-chat"
        data_list = self.wrong2right(content, model)
        try:
            data_list = json.loads(data_list)
        except:
            match = re.search(r'\[[\s\S]*\]', data_list)
            data_list = json.loads(match.group(0))
        return Response(data_list, status=status.HTTP_200_OK)


# 柱状图
class Bar(APIView):
    def get(self, request):
        bars = models.Chart.objects.all()


class Polish(APIView):

    def post(self, request):
        data = request.data
        content = data.get('content')
        goal = data.get('goal')
        model = data.get('model')
        if not model or model not in ['Pro/deepseek-ai/DeepSeek-V3']:
            model = "THUDM/glm-4-9b-chat"
        if not content:
            return Response({'msg': '请输入内容'}, status=status.HTTP_400_BAD_REQUEST)
        if goal:
            prompt = f"""请将"{content}"帮助我往{goal}方向润色。"""
        else:
            prompt = f"""请将下面的文字续写：{content}"""

        def event_generator():
            response_stream = siliconflow_client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "user", "content": prompt},
                ],
                stream=True,
            )
            while True:
                for chunk in response_stream:
                    if hasattr(chunk, 'choices'):
                        for choice in chunk.choices:
                            if hasattr(choice, 'delta') and hasattr(choice.delta, 'content'):
                                res = base64.b64encode(choice.delta.content.encode()).decode()
                                yield f'data: {res}\n\n'
                yield f'data: [DONE]\n\n'
                break

        response = StreamingHttpResponse(
            event_generator(),
            content_type='text/event-stream;charset=UTF-8',

        )
        response['Cache-Control'] = 'no-cache'
        return response


# OCR
class OCR(APIView):
    def post(self, request):
        # image = request.FILE.get('image')
        image = request.FILES.get('image')
        print(image)

        if not image:
            return Response({'msg': '请上传图片'}, status=status.HTTP_400_BAD_REQUEST)

        # image_path = "本地图片路径"
        # image_bytes = pathlib.Path(image_path).read_bytes()
        # image_base64 = base64.b64encode(image_bytes).decode('ascii')
        # 对图片文件进行base64编码
        image_base64 = base64.b64encode(image.read()).decode('ascii')
        response = self.ocr(image_base64)
        return Response(response, status=status.HTTP_200_OK)

    def ocr(self, image_base64: str):

        API_URL = "https://jd0864vbiaz2m3g6.aistudio-hub.baidu.com/ocr"

        # 设置鉴权信息
        headers = {
            "Authorization": f"token {settings.ACCESS_TOKEN}",
            "Content-Type": "application/json"
        }

        # 对本地图片进行Base64编码
        # image_path = "本地图片路径"
        # image_bytes = pathlib.Path(image_path).read_bytes()
        # image_base64 = base64.b64encode(image_bytes).decode('ascii')

        # 设置请求体
        payload = {
            "image": image_base64  # Base64编码的文件内容或者文件链接
        }
        # payload = json.dumps(payload)
        # 调用
        resp = requests.post(url=API_URL, json=payload, headers=headers)
        # 处理接口返回数据
        try:

            result = resp.json()["result"]
            # output_image_path = "output.jpg"
            # with open(output_image_path, "wb") as f:
            #     f.write(base64.b64decode(result["image"]))
            # print(f"OCR结果图保存在 {output_image_path}")
            # 返回识别图的base64编码
            # return result["image"]
            pprint.pp(result['texts'])
            # return {'texts': result['texts'], 'image': result['image']}
            return {'texts': result['texts']}
        except Exception as e:
            return {'msg': '图片识别失败'}


# ChatOCR
class ChatOCR(APIView):
    def post(self, request):
        """
        :param
        request: 请求
        doc：图片url
        prompt：对话提示词
        word_boxes：识别参数
        :return:
        """
        data = request.data
        doc = data.get('doc')
        prompt = data.get('prompt')
        word_boxes = data.get('word_boxes')
        if not prompt:
            return Response({'msg': '请输入对话提示词'}, status=status.HTTP_400_BAD_REQUEST)

        url = settings.CHATOCR
        body = {
            "prompt": prompt,
        }
        if word_boxes:
            body['word_boxes'] = word_boxes
        if doc:
            body['doc'] = doc
        response = requests.post(url, json=body)
        # 如果有返回值
        if response:
            return Response(response.json(), status=status.HTTP_200_OK)
        else:
            return Response({'msg': 'None'}, status=status.HTTP_400_BAD_REQUEST)


# 目标检测

class ObjectDetection(APIView):
    def post(self, request):
        image = request.FILES.get('image')
        if not image:
            return Response({'msg': '请上传图片'}, status=status.HTTP_400_BAD_REQUEST)

        # 对图片文件进行base64编码
        image_base64 = base64.b64encode(image.read()).decode('ascii')
        response = self.objectdetection(image_base64)
        return Response(response, status=status.HTTP_200_OK)

    def objectdetection(self, image_base64: str):

        API_URL = "https://wfu7d3udt0ja02e1.aistudio-hub.baidu.com/objectdetection"

        # 设置鉴权信息
        headers = {
            "Authorization": f"token {settings.ACCESS_TOKEN}",
            "Content-Type": "application/json"
        }

        # 设置请求体
        payload = {
            "image": image_base64  # Base64编码的文件内容或者文件链接
        }

        # 调用
        response = requests.post(url=API_URL, json=payload, headers=headers)

        # 解析接口返回数据
        # 处理接口返回数据
        try:
            response = json.loads(response.content)
            bbox_result = response["result"]["bboxResult"]
            image_base64 = response["result"]["image"]
            return {'bbox': bbox_result, 'image': image_base64}
        except Exception as e:
            return {'msg': '图片识别失败'}


class MysystemAPIView(APIView):
    def post(self, request):
        data = request.data
        content = data.get('content')
        system = data.get('system')
        model = data.get('model')
        # 温度
        try:
            temperature = int(data.get('temperature', 0.7))
        except:
            temperature = 0.7
        if not content:
            return Response({'msg': '请输入内容'}, status=status.HTTP_400_BAD_REQUEST)
        if not system:
            return Response({'msg': '请输入system'}, status=status.HTTP_400_BAD_REQUEST)

        def event_generator():
            # 根据model选择client
            if not model or model == "THUDM/glm-4-9b-chat":
                client = siliconflow_client
            elif model == "deepseek-chat":
                client = deepseek_client
            else:
                return Response({'msg': '请输入正确的model'}, status=status.HTTP_400_BAD_REQUEST)

            response_stream = client.chat.completions.create(
                model="deepseek-chat" if client == deepseek_client else "THUDM/glm-4-9b-chat",
                messages=[
                    {"role": "system", "content": f"""{system}"""},
                    {"role": "user", "content": f"""{content}"""},
                ],
                temperature=temperature,
                stream=True,
            )
            while True:
                for chunk in response_stream:
                    if hasattr(chunk, 'choices'):
                        for choice in chunk.choices:
                            if hasattr(choice, 'delta') and hasattr(choice.delta, 'content'):
                                res = base64.b64encode(choice.delta.content.encode()).decode()
                                yield f'data: {res}\n\n'
                yield f'data: [DONE]\n\n'
                break

        response = StreamingHttpResponse(
            event_generator(),
            content_type='text/event-stream;charset=UTF-8',
        )
        response['Cache-Control'] = 'no-cache'
        return response


class SpeechAPIView(APIView):
    def post(self, request):
        data = request.data
        audio_base64 = data.get("audio")
        audio_format = data.get("audio_format", "wav")
        sample_rate = data.get("sample_rate", 16000)
        sample_rate = int(sample_rate)
        lang = data.get("lang", "zh_cn")
        punc = data.get("punc", 0)
        # 转换为bool
        punc = punc == "true"

        if audio_base64 is None:
            return Response({'msg': '请上传音频'}, status=status.HTTP_400_BAD_REQUEST)

        url = f"{settings.SPEECH}/asr/"
        payload = {
            "audio": audio_base64,
            "audio_format": audio_format,
            "sample_rate": sample_rate,
            "lang": lang,
            "punc": True
        }

        headers = {
            "Content-Type": "application/json"
        }

        resp = requests.post(url=url, json=payload, headers=headers)
        json_string = resp.content.decode('utf-8')
        json_data = json.loads(json_string)
        return Response(json_data, status=status.HTTP_200_OK)


# 代码补全（简要版）
class CodeCompletion_1_APIView(APIView):
    def post(self, request):
        data = request.data
        s = data.get('s')
        eol = data.get('eol')
        if not s or not eol:
            return Response({'msg': '请输入内容'}, status=status.HTTP_400_BAD_REQUEST)

        url = f"{settings.CODE_COMPLETION_1}/code/"
        payload = {
            "s": s,
            "eol": eol
        }

        headers = {
            "Content-Type": "application/json"
        }

        resp = requests.post(url=url, json=payload, headers=headers)
        resp['s'] = s
        return Response(resp, status=status.HTTP_200_OK)


# 通用表格识别
class TableAPIView(APIView):
    def post(self, request):
        image_base64 = request.data.get('image')
        if not image_base64:
            return Response({'msg': '请上传图片base64编码'}, status=status.HTTP_400_BAD_REQUEST)
        response = self.table(image_base64)
        return Response(response, status=status.HTTP_200_OK)

    def table(self, image_base64: str):

        API_URL = settings.TABLE

        # 设置鉴权信息
        headers = {
            "Authorization": f"token {settings.ACCESS_TOKEN}",
            "Content-Type": "application/json"
        }

        # 设置请求体
        payload = {
            "image": image_base64  # Base64编码的文件内容或者文件链接
        }

        # 调用
        resp = requests.post(url=API_URL, json=payload, headers=headers)

        # 解析接口返回数据
        try:
            result = resp.json()["result"]
            return {'tables': result['tables']}
        except Exception as e:
            return {'msg': '图片识别失败'}


# 图片识别文档
class DocumentOCRAPIView(APIView):
    def post(self, request):
        file = request.FILES.get('file')
        if not file:
            return Response({'msg': '请上传图片'}, status=status.HTTP_400_BAD_REQUEST)
        url = settings.DOCUMENT_OCR
        files = {"file": file}
        response = requests.post(url=url, files=files)
        # 检验是否为空
        if response.content == b'':
            return Response({'msg': '图片识别失败'}, status=status.HTTP_400_BAD_REQUEST)
        # 解析接口返回数据

        return Response(response.json(), status=status.HTTP_200_OK)


## 生成日报
class GenerateTodayReportAPIView(APIView):
    def get(self, request):
        uid = request.user.id
        task_items = get_task_items_for_today(uid=uid)
        # 使用/n将task_items列表中的内容拼接起来
        content = '\n'.join(task_items)

        timeout = 6
        result_queue = queue.Queue()
        should_stop = threading.Event()

        def worker():
            # 调用 erniebot 接口生成日报
            response_stream = erniebot.ChatCompletion.create(
                model='ernie-3.5',
                messages=[{'role': 'user', 'content': f"""{content}"""}],
                system='你是一个日报生成机器人，可以根据我给予的内容生成今日的日报，重点在于总结今日的工作内容，并且分条陈述',
                stream=True,
            )

            try:
                while not should_stop.is_set():
                    response = next(response_stream)
                    if response.get_result() == '':
                        logger.warning('Empty response')
                    else:
                        # 将结果 base64 加密
                        res = base64.b64encode(response.get_result().encode()).decode()
                        # 把结果放入队列
                        result_queue.put(res)

            except StopIteration:
                # 结束标志
                result_queue.put('[DONE]')

            finally:
                should_stop.set()

        def event_generator():
            # 开始生成器线程
            generator_thread = threading.Thread(target=worker)
            generator_thread.start()

            while True:
                try:
                    # 阻塞等待结果，直到超时
                    result = result_queue.get(timeout=timeout)
                    if result == '[DONE]':
                        break
                    yield f'data: {result}\n\n'

                except queue.Empty:
                    should_stop.set()
                    generator_thread.join(timeout=0.1)  # 尝试优雅地结束线程
                    yield 'data: [DONE]\n\n'
                    break

        response = StreamingHttpResponse(
            event_generator(),
            content_type='text/event-stream;charset=UTF-8',

        )
        response['Cache-Control'] = 'no-cache'
        return response


# 生成周报
class GenerateWeekReportAPIView(APIView):
    def get(self, request):
        uid = request.user.id
        task_items_dict = get_task_items_for_week(uid=uid)
        data = []
        # 循环获取dict的键值
        for key, value in task_items_dict.items():
            value_content = '\n'.join(value)
            foo = f"{key}: {value_content} \n\n"
            logger.info(foo)
            data.append(foo)

        content = '\n'.join(data)

        timeout = 6
        result_queue = queue.Queue()
        should_stop = threading.Event()  # 新增标志变量

        def worker():
            response_stream = erniebot.ChatCompletion.create(
                model='ernie-3.5',
                messages=[{'role': 'user', 'content': f"""{content}"""}],
                system='你是一个周报生成机器人，可以根据我给予的内容生成本周的周报，重点在于总结本周的工作内容，并且分条陈述',
                stream=True,
            )

            try:
                while not should_stop.is_set():
                    response = next(response_stream)
                    if response.get_result() == '':
                        logger.warning('Empty response')
                    else:
                        # 将结果 base64 加密
                        res = base64.b64encode(response.get_result().encode()).decode()
                        # 把结果放入队列
                        result_queue.put(res)
            except StopIteration:
                # 结束标志
                result_queue.put('[DONE]')
            finally:
                should_stop.set()  # 设置标志

        def event_generator():
            # 开始生成器线程
            generator_thread = threading.Thread(target=worker)
            generator_thread.start()

            while True:
                try:
                    # 阻塞等待结果，直到超时
                    result = result_queue.get(timeout=timeout)
                    if result == '[DONE]':
                        break
                    yield f'data: {result}\n\n'

                except queue.Empty:
                    should_stop.set()  # 设置标志
                    generator_thread.join(timeout=0.1)  # 尝试优雅地结束线程
                    yield 'data: [DONE]\n\n'
                    break

        response = StreamingHttpResponse(
            event_generator(),
            content_type='text/event-stream;charset=UTF-8',

        )
        response['Cache-Control'] = 'no-cache'
        return response


# AI函数
## 生成今日工作计划
def generate_today_plan(uid, timeout=6):
    # 获取用户今日工作计划
    task_items = get_todo_task_items_for_today(uid=uid)
    if not task_items:
        msg_list = ['你好', '今天没有工作计划']

        def event_generator():
            for msg in msg_list:
                res = base64.b64encode(msg.encode()).decode()
                yield f'data: {res}\n\n'

        return event_generator

    # 使用/n将task_items列表中的内容拼接起来
    content = '\n\n\n'.join(task_items)
    # 调用erniebot接口生成日报
    result_queue = queue.Queue()
    should_stop = threading.Event()  # 新增标志变量

    def worker():
        # 调用 erniebot 接口生成日报
        response_stream = erniebot.ChatCompletion.create(
            model='ernie-4.0',
            messages=[{'role': 'user', 'content': f"{content}"}],
            system='你是一个工作计划生成机器人，可以根据我给予的内容生成今日的工作计划，重点在于统筹工作的开展顺序，以及每项工作如何去做，并且分条陈述',
            stream=True,
        )

        try:
            while not should_stop.is_set():
                response = next(response_stream)
                if response.get_result() == '':
                    logger.warning('Empty response')
                    raise StopIteration

                else:
                    # 将结果 base64 加密
                    res = base64.b64encode(response.get_result().encode()).decode()
                    # 把结果放入队列
                    result_queue.put(res)
        except StopIteration:
            # 结束标志
            result_queue.put('[DONE]\n\n')
        finally:
            should_stop.set()  # 设置标志

    def event_generator():
        # 开始生成器线程
        generator_thread = threading.Thread(target=worker)
        generator_thread.start()
        while True:
            try:
                # 阻塞等待结果，直到超时
                result = result_queue.get(timeout=timeout)

                if result == '[DONE]':
                    break
                yield f'data: {result}\n\n'
            except queue.Empty:
                # 如果没有活动超过指定时间，终止线程
                should_stop.set()  # 设置标志
                logger.warning("Stream has been idle for too long, terminating.")
                generator_thread.join(timeout=0.1)  # 尝试优雅地结束线程
                yield 'data: [DONE]\n\n'
                break

    return event_generator


## AI智能搜索
# def search_by_ai(uid, des):

## 返回日期为date的所有工作项
def search_task_items_by_date(uid, date):
    if not date:
        date = datetime.now().date().strftime("%Y-%m-%d")
    items_list = get_task_items_by_date(uid=uid, date=date)
    return items_list


def get_date():
    """
    获取日期，格式为YYYY-MM-DD
    :return:
    """
    today = datetime.now().date().strftime("%Y-%m-%d")
    return f"今天是{today}， "


functions = [
    {
        "name": "generate_today_plan",
        "description": "获取今日工作计划",
        "parameters": {
            "type": "object",
            "properties": {}
        },
        "responses": {
            "type": "object",
            "properties": {
                "msg": {
                    "type": "string",
                    "description": "今日工作计划内容"
                }
            }
        },
    },
    {
        "name": "search_task_items_by_date",
        "description": "获取指定日期的所有工作项",
        "parameters": {
            "type": "object",
            "properties": {
                "date": {
                    "type": "string",
                    "description": "日期，格式为YYYY-MM-DD",
                    "format": "date"
                }
            },
            "required": [
                "date"
            ],
        },

        "responses": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "task_id": {"type": "integer"},
                    "task_item_id": {"type": "string"},
                    "task_title": {"type": "string"},
                    "task_item_title": {"type": "string"},
                    "desc": {"type": "string"},
                    "status": {"type": "string"}
                }
            }
        },
    },
]


class AIAssistantAPIView(APIView):
    def post(self, request):
        """
        AI助理
        :param request: 请求体
        :param type：助手类型
        :param des: 描述
        :param context: 上下文
        :return:
        """
        uid = request.user.id
        # 获取参数
        data = request.data
        # 类型
        ai_type = data.get("type", "talk")
        des = data.get("des")
        # 内容
        context = data.get("context")
        # 上下文

        if ai_type == "talk":
            if context is None:
                return Response({"msg": "请输入聊天内容"})

            response_stream = erniebot.ChatCompletion.create(
                model="ernie-3.5",
                messages=context,
                system="你是一个智慧笔匠AI助手, 功能包括：1、聊天；2、根据日期查询工作项；3、生成工作计划；4、制定工作日程，等等",
                stream=True)

            def event_generator():
                while True:
                    try:
                        response = next(response_stream)
                        if response.get_result() == '':
                            logger.warning(f'Empty response')
                            raise StopIteration
                        # 将结果base64加密
                        res = base64.b64encode(response.get_result().encode()).decode()
                        yield f'data: {res}\n\n'
                    except StopIteration:
                        yield f'data: [DONE]\n\n'
                        break

            response = StreamingHttpResponse(
                event_generator(),
                content_type='text/event-stream;charset=UTF-8',
            )
            response['Cache-Control'] = 'no-cache'
            return response

        else:

            if ai_type == "generate_today_plan":
                response = erniebot.ChatCompletion.create(
                    model="ernie-3.5",
                    messages=[{
                        "role": "user",
                        "content": f"{ai_type}: {des}"
                    }],
                    functions=[functions[0]],
                    stream=False)
                # assert hasattr(response, "function_call")
                if not hasattr(response, "function_call"):
                    logger.info("No function call")
                    return Response({"msg": "No function call"})
                function_call = response.function_call
                args = json.loads(function_call["arguments"])
                logger.info(args)
                args["uid"] = uid
                res = generate_today_plan(**args)
                response = StreamingHttpResponse(
                    res(),
                    content_type='text/event-stream;charset=UTF-8',
                )
                response['Cache-Control'] = 'no-cache'
                return response

            # 前置参数处理
            elif ai_type == "search_task_items_by_date":
                des = get_date() + des
                response = erniebot.ChatCompletion.create(
                    model="ernie-3.5",
                    messages=[{
                        "role": "user",
                        "content": f"{ai_type}: {des}"
                    }],
                    functions=[functions[1]],
                    stream=False)

                if not hasattr(response, "function_call"):
                    logger.info("No function call")
                    return Response({"msg": "No function call"})
                function_call = response.function_call
                args = json.loads(function_call["arguments"])
                logger.info(args)
                args["uid"] = uid
                res = search_task_items_by_date(**args)
                return Response(res)


# 获取AI作画access_token
def get_access_token():
    # 获取参数
    api_key = "FWWd4BiA1xxXBIX75a7mhlNm"
    secret_key = "Td1yVL2cmexR5zdorS1UJ3LOLjCpqe7O"
    url = f"https://aip.baidubce.com/oauth/2.0/token?grant_type=client_credentials&client_id={api_key}&client_secret={secret_key}"

    payload = ""
    headers = {
        'Content-Type': 'application/json',
        'Accept': 'application/json'
    }

    response = requests.request("POST", url, headers=headers, data=payload)
    res = response.json()
    if res.get("error"):
        logger.info(res.get("error_description"))
        raise Exception(res.get("error_description"))
    logger.info(res)
    return res["access_token"]


def draw(text, style="二次元", resolution="1024*1024", num=1):
    access_token = get_access_token()
    url = f"https://aip.baidubce.com/rpc/2.0/wenxin/v1/basic/textToImage?access_token={access_token}"
    logger.info(url)
    headers = {
        'Content-Type': 'application/json',
    }
    body = {
        "text": text,
        "style": style,
        "resolution": resolution,
        "num": num
    }
    logger.info(body)
    response = requests.post(url=url, headers=headers, json=body)
    res = response.json()
    logger.info(res)
    if res.get("data") and res.get("data").get("taskId"):
        return res["data"]["taskId"]
    else:
        logger.info(res)
        raise Exception("AI作画失败")


class DrawAPIView(APIView):

    def post(self, request):
        """
        生成图片，返回taskId
        :param request:
        :return:
        """
        data = request.data
        text = data.get("text")
        style = data.get("style", "二次元")
        resolution = data.get("resolution", "1024*1024")
        num = int(data.get("num", 1))
        task_id = draw(text, style=style, resolution=resolution, num=num)
        return Response({"taskId": str(task_id)})

    def get(self, request):
        task_id = request.GET.get("taskId")
        if task_id is None:
            return Response({"msg": "taskId不能为空"}, status=400)
        if isinstance(task_id, str):
            task_id = int(task_id)
        access_token = get_access_token()
        url = f"https://aip.baidubce.com/rpc/2.0/wenxin/v1/basic/getImg?access_token={access_token}"
        headers = {
            'Content-Type': 'application/json',
        }
        body = {
            "taskId": task_id
        }
        response = requests.post(url=url, headers=headers, json=body)
        res = response.json()
        return Response(res, status=200)


class ImageAgentAPIView(APIView):
    def get(self, request):
        """
        访问图片代理
        :param request:
        :return:
        """
        image_url = request.query_params.get("url")
        if image_url is None:
            return Response({"msg": "url不能为空"}, status=400)

        try:
            response = requests.get(image_url, stream=True)
            response.raise_for_status()

            # 设置响应类型和头信息
            django_response = HttpResponse(
                content_type=response.headers.get('Content-Type')
            )

            # 过滤并设置响应头
            for header, value in response.headers.items():
                if header.lower() not in ('content-length', 'content-encoding', 'transfer-encoding', 'connection'):
                    django_response[header] = value

            # 将图片数据流式传输给客户端
            for chunk in response.iter_content(chunk_size=8192):
                django_response.write(chunk)

            return django_response

        except requests.RequestException as e:
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# 解析视频字幕
class VideoOCRAPIView(APIView):
    def post(self, request):
        video = request.FILES.get('video')
        url = "https://c2iajez5h2y9a5g1.aistudio-hub.baidu.com/video/"
        files = {
            'video': video
        }
        response = requests.post(url, files=files)
        if response.status_code == 200:
            res = response.text
            return Response({'msg': res}, status=status.HTTP_200_OK)
        return Response({'msg': '解析失败'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# COZE 工作流接口
class CozeFunctionCallAPIView(APIView):
    def get_access_token(self):
        access_token = connect_coze()
        if access_token:
            return access_token
        return None

    def post(self, request):
        data = request.data
        input = data.get('input')
        if not input:
            return Response({'msg': '请输入内容'}, status=status.HTTP_400_BAD_REQUEST)
        text = data.get('text')
        html_text = data.get('html_text')
        if not text and not html_text:
            return Response({'msg': '请输入文本或html文本'}, status=status.HTTP_400_BAD_REQUEST)
        access_token = self.get_access_token()
        if not access_token:
            return Response({'msg': '获取access_token失败'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        url = "https://api.coze.cn/v1/workflow/run"
        header = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {access_token}"
        }
        data = {
            "workflow_id": "7480013157751783443",
            "parameters": {
                "input": f"""{input}""",
                "text": f"""{text}""",
                "html_text": f"""{html_text}"""
            }
        }
        resp = requests.post(url, headers=header, json=data)
        # 解析接口返回数据
        try:
            res = resp.json()
            if res.get("code") != 0:
                return Response({'msg': '调用失败'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
            data = json.loads(res.get('data'))
            function_call_list = data.get('function_call_list')
            return Response({'function_call_list': function_call_list}, status=status.HTTP_200_OK)

        except Exception as e:
            print(e)
            return Response({'msg': '调用失败'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    # 生成证件照


class IDPhotoAPIView(APIView):
    def post(self, request):
        # 获取照片
        image = request.FILES.get('image')
        if not image:
            return Response({'msg': '请上传图片'}, status=status.HTTP_400_BAD_REQUEST)
        color = request.data.get('color', '蓝色')
        if color not in ['蓝色', '红色', '白色', "灰色", "浅蓝"]:
            return Response({'msg': '颜色错误'}, status=status.HTTP_400_BAD_REQUEST)
        # 访问获取图片链接的API
        temp_api_url = "https://api.daoxuan.cc/python/image/upload/temp"
        files = {
            'file': image
        }
        response = requests.post(temp_api_url, files=files)
        if response.status_code != 200:
            return Response({'msg': '上传图片失败'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        res = response.json()
        print(res)
        image_url = res.get('filepath')

        # 调用api
        access_token = connect_coze()
        if not access_token:
            return Response({'msg': '获取access_token失败'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        url = "https://api.coze.cn/v1/workflow/run"
        header = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {access_token}"
        }
        data = {
            "workflow_id": "7481473142122102835",
            "parameters": {
                "image": f"https://api.daoxuan.cc/python/{image_url}",
            }
        }

        resp = requests.post(url, headers=header, json=data)
        # 解析接口返回数据
        res = resp.json()
        # {
        #     "res": {
        #         "code": 0,
        #         "cost": "0",
        #         "data": "{\"output\":\"https://s.coze.cn/t/IM7zHkXKm3E/\"}",
        #         "debug_url": "https://www.coze.cn/work_flow?execute_id=7482647390299127858&space_id=7477774402705424420&workflow_id=7481473142122102835&execute_mode=2",
        #         "msg": "Success",
        #         "token": 0
        #     }
        # }
        if res.get('code') != 0:
            return Response({'msg': '生成失败'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        data = json.loads(res.get('data'))
        output = data.get('output')
        # 下载图片
        response = requests.get(output)
        if response.status_code != 200:
            return Response({'msg': '下载图片失败'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        # 使用下载后的图片作为参数调用图片换底API
        # 将下载的图片内容转换为文件对象
        image_file = BytesIO(response.content)
        url = "https://api.daoxuan.cc/python/resume/id_photo_no_cut"
        # 构建请求数据
        files = {
            "image": ("image.jpg", image_file, "image/jpeg")  # 文件字段名必须与 API 参数名一致
        }
        data = {
            'color': color  # 提供 color 参数
        }
        response = requests.post(url, files=files, data=data)
        if response.status_code != 200:
            return Response({'msg': '生成失败'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        # 返回图片内容
        return FileResponse(BytesIO(response.content), content_type="image/jpeg")


def dialogue_new(self, request):
    # uuid生成随机字符串
    dialogue_id = str(uuid.uuid4())
    return HttpResponse(dialogue_id)


# 开始对话，返回对话id
class ContextAPIView(APIView):
    def new(self):
        # uuid生成随机字符串
        dialogue_id = str(uuid.uuid4())
        return dialogue_id

    def post(self, request, type):
        user_id = request.user.id
        data = request.data
        if type == 'new':
            dialogue_id = self.new()
            system_string = data.get('system')
            if system_string:
                models.Conversation.objects.create(user_id=user_id, dialogue_id=dialogue_id, system=system_string)
            else:
                models.Conversation.objects.create(user_id=user_id, dialogue_id=dialogue_id)
            response = {
                'dialogue_id': dialogue_id,
            }
            return Response(response, status=status.HTTP_201_CREATED)
        if type == 'chat':
            dialogue_id = data.get('dialogue_id')
            if not dialogue_id:
                return Response({'error': '没有上传dialogue_id'}, status=status.HTTP_400_BAD_REQUEST)
            message = data.get('message')
            if not message:
                return Response({'error': '没有上传message'}, status=status.HTTP_400_BAD_REQUEST)
            conversation = models.Conversation.objects.filter(dialogue_id=dialogue_id).first()
            if not conversation:
                return Response({'error': '对话不存在'}, status=status.HTTP_400_BAD_REQUEST)
            # [{"role": "system", "content": f"""{system}"""},{'role':'user', "content":""},{'role':'assistant', "content":""}]
            system_string = conversation.system
            dialogue = conversation.dialogue
            if system_string:
                history = [{"role": "system", "content": f"""{system_string}"""}]
            else:
                history = []
            try:
                if dialogue:
                    dialogue = json.loads(dialogue)
                    history += dialogue
                message_dict = {"role": "user", "content": f"""{message}"""}
                history.append(message_dict)

                # 本次对话内容
                def event_generator():
                    dialogue_this_time = ""
                    response_stream = deepseek_client.chat.completions.create(
                        model="deepseek-chat",
                        messages=history,
                        stream=True,
                    )
                    while True:
                        for chunk in response_stream:
                            if hasattr(chunk, 'choices'):
                                for choice in chunk.choices:
                                    if hasattr(choice, 'delta') and hasattr(choice.delta, 'content'):
                                        dialogue_this_time += choice.delta.content
                                        res = base64.b64encode(choice.delta.content.encode()).decode()
                                        yield f'data: {res}\n\n'
                        history.append({"role": "assistant", "content": f"""{dialogue_this_time}"""})
                        conversation.dialogue = json.dumps(history)
                        conversation.save()
                        yield f'data: [DONE]\n\n'
                        break

                response = StreamingHttpResponse(
                    event_generator(),
                    content_type='text/event-stream;charset=UTF-8',
                )
                response['Cache-Control'] = 'no-cache'
                return response

            except Exception as e:
                return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        return Response({'error': 'type错误'}, status=status.HTTP_400_BAD_REQUEST)


# response = client.completions.create(
#     model="deepseek-chat",
#     prompt="""在一个遥远的王国里，""",
#     # suffix=" ",
# )
# 对话补全
class CompletionsAPIView(APIView):
    def fim(self, prompt, suffix, token):
        client = OpenAI(
            api_key=settings.DeepSeek_APIKEY,
            base_url=settings.DeepSeek_Completion_URL,
        )
        if token:
            response_stream = client.completions.create(
                model="deepseek-chat",
                prompt=f"""{prompt}""",
                suffix=f"""{suffix}""",
                max_tokens=token,
                stream=True,
            )
        else:
            response_stream = client.completions.create(
                model="deepseek-chat",
                prompt=f"""{prompt}""",
                suffix=f"""{suffix}""",
                stream=True,
            )
        while True:
            # print("response_stream", response_stream)
            for chunk in response_stream:
                if hasattr(chunk, 'choices'):
                    for choice in chunk.choices:
                        if hasattr(choice, 'text'):
                            print(choice.text, end='')
                            res = base64.b64encode(choice.text.encode()).decode()
                            yield f'data: {res}\n\n'
            yield f'data: [DONE]\n\n'
            break

    def prefix(self, prompt, token):
        client = OpenAI(
            api_key=settings.DeepSeek_APIKEY,
            base_url=settings.DeepSeek_Completion_URL,
        )
        messages = [
            {"role": "user", "content": """补全文本，不使用markdown语法"""},
            {"role": "assistant",
             "content": f"""{prompt}""",
             "prefix": True}
        ]
        if token:
            response_stream = client.chat.completions.create(
                model="deepseek-chat",
                messages=messages,
                max_tokens=token,
                stream=True,
            )
        else:
            response_stream = client.chat.completions.create(
                model="deepseek-chat",
                messages=messages,
                stream=True,
            )
        while True:
            for chunk in response_stream:
                if hasattr(chunk, 'choices'):
                    for choice in chunk.choices:
                        print(choice.delta.content, end="", flush=True)
                        res = base64.b64encode(choice.delta.content.encode()).decode()
                        yield f'data: {res}\n\n'
            yield f'data: [DONE]\n\n'
            break

    def post(self, request):
        data = request.data
        prompt = data.get('prompt', "")
        if not prompt:
            return Response({'error': '没有上传prompt'}, status=status.HTTP_400_BAD_REQUEST)
        token = data.get('token', 128)
        # 尝试转换为整数token
        try:
            token = int(token)
        except:
            token = None
        suffix = data.get('suffix')

        if suffix:
            response = StreamingHttpResponse(
                self.fim(prompt, suffix, token),
                content_type='text/event-stream;charset=UTF-8',
            )
        else:
            response = StreamingHttpResponse(
                self.prefix(prompt, token),
                content_type='text/event-stream;charset=UTF-8',
            )
        response['Cache-Control'] = 'no-cache'
        return response

# coze 工作流调用：搜索相关文档
class CozeSearchAPIView(APIView):
    def get_access_token(self):
        access_token = connect_coze()
        if access_token:
            return access_token
        return None
    def post(self, request):
        data = request.data
        if not data:
            return Response({'error': '没有上传数据'}, status=status.HTTP_400_BAD_REQUEST)
        if not data.get('input'):
            return Response({'error': '没有上传input'}, status=status.HTTP_400_BAD_REQUEST)
        access_token = self.get_access_token()
        if not access_token:
            return Response({'error': '获取access_token失败'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        url = "https://api.coze.cn/v1/workflow/run"
        header = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {access_token}"
        }
        data = {
            "workflow_id": "7489127750122782774",
            "parameters": {
                "input": data.get('input')
            }
        }
        res = requests.post(url, headers=header, json=data)
        try:
            res = res.json()
            response = json.loads(res.get('data'))
        except:
            res = res.text
            response = res
        return Response(response, status=status.HTTP_200_OK)



# 知识库

class GenerateWithContextView(APIView):
    parser_classes = [MultiPartParser]

    def post(self, request):
        # 获取请求数据
        prompt = request.data.get('prompt')
        user_text = request.data.get('user_text')
        files = request.FILES.getlist('files')  # 获取多个文件
        urls = request.data.getlist('urls')  # 获取多个URL

        # 准备请求数据
        data = {
            'prompt': prompt,
            'user_text': user_text,
        }
        urls = [url for url in urls if url]
        if urls:
            data['urls'] = urls

        # 准备文件数据
        files_data = None
        if files:
            files_data = [('files', file) for file in files]
        try:
            # 发送请求到FastAPI接口
            fastapi_url = "http://ouc.daoxuan.cc:10008/generate-with-context"
            # fastapi_url = "http://127.0.0.1:8000/generate-with-context"
            response = requests.post(
                fastapi_url,
                data=data,
                files=files_data,
                stream=True
            )

            def generate():
                for chunk in response.iter_content(chunk_size=None):
                    if chunk:
                        yield chunk
                yield 'data: [DONE]\n\n'
            return StreamingHttpResponse(
                generate(),
                content_type='text/event-stream;charset=UTF-8'
            )
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)