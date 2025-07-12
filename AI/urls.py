from django.urls import path
from . import views

urlpatterns = [
    path('translate/', views.Translate.as_view()),
    path('summary/', views.Summary.as_view()),
    path('abstract/', views.Abstract.as_view()),
    path('continue/', views.Continue2Write.as_view()),
    path('wrong2right/', views.Wrong2Right.as_view()),
    path('polish/', views.Polish.as_view()),
    path('ocr/', views.OCR.as_view()),
    path('chatocr/', views.ChatOCR.as_view()),
    path('objectdetection/', views.ObjectDetection.as_view()),
    path('mysystem/', views.MysystemAPIView.as_view()),
    path('speech/', views.SpeechAPIView.as_view()),
    path('table/', views.TableAPIView.as_view()),
    path('codecompletion1/', views.CodeCompletion_1_APIView.as_view()),
    path('document/', views.DocumentOCRAPIView.as_view()),
    path('report/today/', views.GenerateTodayReportAPIView.as_view()),
    path('report/week/', views.GenerateWeekReportAPIView.as_view()),
    path('assistant/', views.AIAssistantAPIView.as_view()),  # 新增AI助理功能
    path('draw/', views.DrawAPIView.as_view()),  # 新增画图功能
    path('image_agent/', views.ImageAgentAPIView.as_view()),  # 新增图像代理功能
    path('video/', views.VideoOCRAPIView.as_view()),  # 新增视频OCR功能')
]
