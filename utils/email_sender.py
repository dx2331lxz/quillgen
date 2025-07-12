import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.application import MIMEApplication
from email.utils import formataddr
import os

class EmailSender:
    def __init__(self):
        # QQ邮箱SMTP服务器配置
        self.smtp_server = 'smtp.qq.com'
        self.smtp_port = 465
        # 使用SSL加密连接
        self.use_ssl = True
        
        # 发件人配置
        self.sender_email = '2872983273@qq.com'  # 替换为你的QQ邮箱
        self.sender_name = '系统通知'
        self.auth_code = 'givlpgsaozanddgb'  # 替换为你的QQ邮箱授权码

    def send_email(self, to_email, subject, content, html=True, attachments=None):
        """
        发送邮件
        :param to_email: 收件人邮箱
        :param subject: 邮件主题
        :param content: 邮件内容
        :param html: 是否为HTML内容
        :param attachments: 附件列表，每个元素为文件路径
        :return: bool, str
        """
        try:
            # 创建邮件对象
            msg = MIMEMultipart()
            msg['From'] = formataddr([self.sender_name, self.sender_email])
            msg['To'] = to_email
            msg['Subject'] = subject

            # 添加邮件正文
            if html:
                msg.attach(MIMEText(content, 'html', 'utf-8'))
            else:
                msg.attach(MIMEText(content, 'plain', 'utf-8'))

            # 添加附件
            if attachments:
                for file_path in attachments:
                    if os.path.exists(file_path):
                        with open(file_path, 'rb') as f:
                            part = MIMEApplication(f.read())
                            part.add_header('Content-Disposition', 'attachment',
                                           filename=os.path.basename(file_path))
                            msg.attach(part)

            # 连接SMTP服务器并发送邮件
            if self.use_ssl:
                smtp = smtplib.SMTP_SSL(self.smtp_server, self.smtp_port)
            else:
                smtp = smtplib.SMTP(self.smtp_server, self.smtp_port)
                smtp.starttls()

            smtp.login(self.sender_email, self.auth_code)
            smtp.send_message(msg)
            smtp.quit()
            return True, '邮件发送成功'

        except Exception as e:
            return False, f'邮件发送失败: {str(e)}'

    def send_verification_email(self, to_email, verification_code):
        """
        发送验证码邮件
        :param to_email: 收件人邮箱
        :param verification_code: 验证码
        :return: bool, str
        """
        subject = '邮箱验证码'
        content = f'''
        <div style="background-color: #f7f7f7; padding: 20px;">
            <h2 style="color: #333;">验证码</h2>
            <p style="font-size: 16px; color: #666;">您的验证码是：</p>
            <div style="background-color: #fff; padding: 10px; margin: 15px 0; border-radius: 5px;">
                <span style="font-size: 24px; color: #007bff; font-weight: bold;">{verification_code}</span>
            </div>
            <p style="font-size: 14px; color: #999;">验证码有效期为5分钟，请尽快使用。</p>
        </div>
        '''
        return self.send_email(to_email, subject, content, html=True)