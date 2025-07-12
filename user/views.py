import smtplib
import socket

import requests
from django.shortcuts import render, HttpResponse
from django.template.loader import render_to_string

from . import models
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status, pagination  # 状态和分页
from rest_framework.parsers import MultiPartParser  # 文件上传`MultiPartParser`解析器
import json
import os
# 导入默认User
from django.contrib.auth.models import User
# jwt
from rest_framework.permissions import AllowAny
from rest_framework.permissions import IsAuthenticated
from rest_framework_simplejwt.authentication import JWTAuthentication, JWTTokenUserAuthentication
from rest_framework_simplejwt.views import TokenObtainPairView
from rest_framework_simplejwt.tokens import RefreshToken
## UNI-SMS
from unisdk.sms import UniSMS
from unisdk.exception import UniException

import logging
from django.core.mail import send_mail

# 获得logger实例
logger = logging.getLogger(__name__)


# 注册账号
class Register(APIView):
    permission_classes = [AllowAny]

    # 检验密码强度
    def check_password(self, password):
        score = 0
        """
        一、密码长度:
            5 分: 小于等于 4 个字符
            10 分: 5 到 7 字符
            25 分: 大于等于 8 个字符
            
            二、字母:
            
            0 分: 没有字母
            10 分: 全都是小（大）写字母20 分: 大小写混合字母
            
            三、数字:
            
            0分: 没有数字
            10分: 1 个数字
            20分: 大于等于 3个数字
            
            四、符号:
            
            0分: 没有符号
            10分: 1个符号
            25分: 大于1个符号
            
            五、奖励:
            
            2分: 字母和数字
            3分: 字母、数字和符号
            5分: 大小写字母、数字和符号
        :param password: 密码
        :return: 分数
        """
        # 长度
        if len(password) <= 4:
            score += 5
        elif 5 <= len(password) <= 7:
            score += 10
        else:
            score += 25

        # 字母
        if password.isalpha():
            score += 0
        elif password.islower() or password.isupper():
            score += 10
        else:
            score += 20

        # 数字
        if password.isdigit():
            score += 0
        elif len([i for i in password if i.isdigit()]) >= 3:
            score += 20
        else:
            score += 10

        # 符号
        if len([i for i in password if i.isalnum()]) == 0:
            score += 0
        elif len([i for i in password if not i.isalnum()]) == 1:
            score += 10
        else:
            score += 25

        # 奖励
        if len([i for i in password if i.isalpha()]) > 0 and len([i for i in password if i.isdigit()]) > 0:
            score += 2
        if len([i for i in password if i.isalpha()]) > 0 and len([i for i in password if i.isdigit()]) > 0 and len(
                [i for i in password if not i.isalnum()]) > 0:
            score += 3
        if len([i for i in password if i.islower()]) > 0 and len([i for i in password if i.isupper()]) > 0 and len(
                [i for i in password if i.isdigit()]) > 0 and len([i for i in password if not i.isalnum()]) > 0:
            score += 5

        return score

    def post(self, request):
        data = request.data
        username = data.get('username')
        password = data.get('password')
        re_password = data.get('re_password')
        if not username or not password:
            return Response({'msg': '请输入用户名和密码'}, status=status.HTTP_400_BAD_REQUEST)
        if password != re_password:
            return Response({'msg': '两次密码不一致'}, status=status.HTTP_400_BAD_REQUEST)
        if User.objects.filter(username=username).exists():
            return Response({'msg': '用户名已存在'}, status=status.HTTP_400_BAD_REQUEST)
        score = self.check_password(password)
        if score < 50:
            return Response({'msg': '密码强度不够'}, status=status.HTTP_400_BAD_REQUEST)

        User.objects.create_user(username=username, password=password)
        return Response({'msg': '注册成功'}, status=status.HTTP_201_CREATED)


# 登录
class LoginAPIView(APIView):
    permission_classes = [AllowAny]

    def post(self, request, *args, **kwargs):
        data = request.data
        try:
            user = User.objects.get(username=data.get('username'))
            if not user.check_password(data.get('password')):
                return Response({'msg': '密码错误'}, status=status.HTTP_400_BAD_REQUEST)

            if request.META.get('HTTP_X_FORWARDED_FOR'):
                ip = request.META.get("HTTP_X_FORWARDED_FOR")
            else:
                ip = request.META.get("HTTP_X_REAL_IP")
            if not ip:
                if 'HTTP_X_FORWARDED_FOR' in request.META:
                    ip = request.META.get('HTTP_X_FORWARDED_FOR')
                else:
                    ip = request.META.get('REMOTE_ADDR')
            if models.LoginRecord.objects.filter(user=user, ip=ip).exists():
                #     查看是否过期
                login_record = models.LoginRecord.objects.filter(user=user, ip=ip).first()
                if login_record.login_time + timezone.timedelta(days=7) < timezone.now():
                    #         过期则需要手机号验证码登录
                    return Response({'msg': '登录过期，请使用手机号验证码登录'}, status=status.HTTP_400_BAD_REQUEST)
            else:
                return Response({'msg': f'当前地址{ip}为新地址登录，请使用手机号验证码登录'},
                                status=status.HTTP_400_BAD_REQUEST)
            refresh = RefreshToken.for_user(user)
            return Response({
                'refresh': str(refresh),
                'access': str(refresh.access_token),
            })

        except User.DoesNotExist:
            return Response({'msg': '用户不存在'}, status=status.HTTP_400_BAD_REQUEST)


# 修改密码
# class ChangePassword(APIView):
#     def get(self, request):
#         user_id = request.user.id
#         user = User.objects.get(id=user_id)
#         # 发送验证码
#         phone_number = user.username
#         resp, verification_code = SendSMSVerificationCode().send_sms(phone_number)
#         ## todo 添加发送短信是否成功的逻辑
#         if resp.SendStatusSet[0].Code == 'Ok':
#             # 记录生成时间和过期时间（60秒后）
#             expiration_time = timezone.now() + timezone.timedelta(minutes=10)
#
#             # 保存验证码到数据库
#             models.PhoneVerification.objects.update_or_create(
#                 phone_number=phone_number,
#                 defaults={'verification_code': verification_code, 'expiration_time': expiration_time}
#             )
#             return Response({'msg': 'Verification code sent'})
#         else:
#             return Response({'msg': f'发送失败,出了点小问题{resp.SendStatusSet[0].Code}', 'code': 403},
#                             status=status.HTTP_403_FORBIDDEN)
#
#     def post(self, request):
#         user_id = request.user.id
#         user = User.objects.get(id=user_id)
#         data = request.data
#         verification_code = data.get('verification_code')
#         if not verification_code:
#             return Response({'msg': '请输入验证码'}, status=status.HTTP_400_BAD_REQUEST)
#         phone_number = user.username
#         try:
#             verification = models.PhoneVerification.objects.get(phone_number=phone_number)
#         except models.PhoneVerification.DoesNotExist:
#             return Response({'msg': '验证码失效，请重新发送验证码'}, status=400)
#
#         now = timezone.now()
#         if verification.expiration_time >= now and verification.verification_code == verification_code:
#             new_password = data.get('new_password')
#             score = Register().check_password(new_password)
#             if score < 50:
#                 return Response({'msg': '密码强度不够'}, status=status.HTTP_400_BAD_REQUEST)
#
#             user.set_password(new_password)
#             user.save()
#             return Response({'msg': '修改密码成功'}, status=status.HTTP_200_OK)
#         else:
#             return Response({'msg': '验证码错误或已超时'}, status=400)


# 上传头像
class Avatar(APIView):
    parser_classes = [MultiPartParser]

    def post(self, request):
        user_id = request.user.id
        user = User.objects.get(id=user_id)
        avatar = request.FILES.get('avatar')
        if not avatar:
            return Response({'msg': '请选择头像'}, status=status.HTTP_400_BAD_REQUEST)
        # 限制上传文件大小

        if avatar.size > 1024 * 1024 * 2:
            return Response({'msg': '图片大小不能超过2M'}, status=status.HTTP_400_BAD_REQUEST)
        # 限制上传文件类型
        ext = os.path.splitext(avatar.name)[1]
        if ext not in ['.jpg', '.jpeg', '.png', '.gif']:
            return Response({'msg': '图片格式不正确'}, status=status.HTTP_400_BAD_REQUEST)
        models.Avatar.objects.update_or_create(user=user, defaults={'avatar': avatar})

        return Response({'msg': '上传头像成功'}, status=status.HTTP_201_CREATED)

    def get(self, request):
        user_id = request.user.id
        user = User.objects.get(id=user_id)
        avatar = models.Avatar.objects.filter(user=user).first()
        if not avatar:
            return Response({'msg': '未上传头像'}, status=status.HTTP_400_BAD_REQUEST)
        return Response({'url': avatar.avatar.url}, status=status.HTTP_200_OK)


#  修改昵称
class Name(APIView):

    def post(self, request):
        user_id = request.user.id
        user = User.objects.get(id=user_id)
        data = request.data
        name = data.get('name')
        if not name:
            return Response({'msg': '请输入昵称'}, status=status.HTTP_400_BAD_REQUEST)
        models.UserInfo.objects.update_or_create(user=user, defaults={'name': name})
        return Response({'msg': '修改昵称成功'}, status=status.HTTP_200_OK)

    #  获取昵称
    def get(self, request):
        user_id = request.user.id
        user = User.objects.get(id=user_id)
        name = models.UserInfo.objects.filter(user=user).first()
        if not name:
            return Response({'msg': '未设置昵称'}, status=status.HTTP_400_BAD_REQUEST)
        return Response({'name': name.name}, status=status.HTTP_200_OK)


# 获取全部用户信息
class UserInfo(APIView):
    def get(self, request):
        user_id = request.user.id
        user = User.objects.get(id=user_id)
        if not user:
            return Response({'msg': '用户不存在'}, status=status.HTTP_400_BAD_REQUEST)
        name = models.UserInfo.objects.filter(user=user).first()
        avatar = models.Avatar.objects.filter(user=user).first()
        res = {
            'name': name.name if name else '',
            'avatar': avatar.avatar.url if avatar else ''
        }
        return Response(res, status=status.HTTP_200_OK)


import random
from Editor import settings
## 引入腾讯云短信
from tencentcloud.common import credential
from tencentcloud.common.exception.tencent_cloud_sdk_exception import TencentCloudSDKException
# 导入对应产品模块的client models。
from tencentcloud.sms.v20210111 import sms_client
from tencentcloud.sms.v20210111.models import SendSmsRequest
from tencentcloud.common.profile.client_profile import ClientProfile
from tencentcloud.common.profile.http_profile import HttpProfile
# 导入时区
from django.utils import timezone


class SendVerificationCode(APIView):
    permission_classes = [AllowAny]
    
    def send_email(self, email):
        try:
            # 生成随机的验证码
            verification_code = str(random.randint(100000, 999999))
            while True:
                if models.EmailVerification.objects.filter(verification_code=verification_code).exists():
                    verification_code = str(random.randint(100000, 999999))
                else:
                    break

            # 准备邮件内容
            subject = '验证码邮件'
            html_content = render_to_string('email/verification_email.html', {'verification_code': verification_code})
            plain_content = f"""
                尊敬的用户，您好！

                您正在注册或登录我们的编辑器服务，以下是您的验证码：

                {verification_code}

                请在 10 分钟内使用该验证码完成验证。

                如果您未进行此操作，请忽略此邮件。

                此邮件由系统自动发送，请勿直接回复。

                © 2025 爱特工作室. 保留所有权利。
                """

            # 使用自定义邮件发送类
            from utils.email_sender import EmailSender
            email_sender = EmailSender()
            success, message = email_sender.send_email(
                to_email=email,
                subject=subject,
                content=html_content,
                html=True
            )

            if success:
                return True, verification_code
            else:
                logger.error(f"邮件发送失败: {message}")
                return False, None

        except Exception as e:
            logger.error(f"发送邮件时发生未知错误: {e}", exc_info=True)
            return False, None

    def get(self, request):
        # phone = request.query_params.get('phone')
        email = request.query_params.get('email')
        # if not phone:
        #     return Response({'msg': '请输入手机号', 'code': 403}, status=status.HTTP_403_FORBIDDEN)
        if not email:
            return Response({'msg': '请输入邮箱', 'code': 403}, status=status.HTTP_403_FORBIDDEN)
        # 发送验证码
        # resp, verification_code = self.send_sms(phone)
        resp, verification_code = self.send_email(email)
        if resp:
            # 记录生成时间和过期时间（60秒后）
            expiration_time = timezone.now() + timezone.timedelta(minutes=10)

            # 保存验证码到数据库
            # models.PhoneVerification.objects.update_or_create(
            #     phone_number=email,
            #     defaults={'verification_code': verification_code, 'expiration_time': expiration_time}
            # )
            models.EmailVerification.objects.update_or_create(
                email=email,
                defaults={'verification_code': verification_code, 'expiration_time': expiration_time}
            )
            return Response({'msg': 'Verification code sent'})
        else:
            return Response({'msg': f'发送失败,出了点小问题', 'code': 403},
                            status=status.HTTP_403_FORBIDDEN)

    def post(self, request):
        # phone_number = request.data.get('phone')
        email = request.data.get('email')
        verification_code = request.data.get('verification_code')

        # 在数据库中验证验证码
        if not email or not verification_code:
            return Response({'msg': '邮箱或验证码为空', 'code': 403}, status=status.HTTP_403_FORBIDDEN)
        try:
            # verification = models.PhoneVerification.objects.get(phone_number=phone_number)
            verification = models.EmailVerification.objects.get(email=email)
        except models.EmailVerification.DoesNotExist:
            return Response({'msg': '验证码失效，请重新发送验证码'}, status=400)

        now = timezone.now()
        if verification.expiration_time >= now and verification.verification_code == verification_code:
            try:
                #     查看是否有这个用户，没有则创建然后登录成功，有则登录成功
                user = User.objects.get(username=email)
            except User.DoesNotExist:
                user = User.objects.create_user(username=email, password=email)
            # #     记录登录ip
            # if request.META.get('HTTP_X_FORWARDED_FOR'):
            #     ip = request.META.get("HTTP_X_FORWARDED_FOR")
            # else:
            #     ip = request.META.get("HTTP_X_REAL_IP")
            # models.LoginRecord.objects.update_or_create(user=user, defaults={'ip': ip})
            refresh = RefreshToken.for_user(user)
            return Response({
                'refresh': str(refresh),
                'access': str(refresh.access_token),
            })
        else:
            return Response({'msg': '验证码错误或已超时'}, status=400)
