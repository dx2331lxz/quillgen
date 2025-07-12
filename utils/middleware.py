"""日志记录中间键，用于记录请求日志"""
import logging

# 创建一个日志记录器
logger = logging.getLogger(__name__)

class RequestLoggingMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # 在请求被处理之前记录日志
        logger.info(
            f"Received {request.method} request to {request.path} from {request.user.id} with query params: {request.GET} and POST data: {request.POST}")

        # 让请求继续向下传递
        response = self.get_response(request)

        # 在请求被处理之后也可以添加额外的日志记录（如果需要）

        return response