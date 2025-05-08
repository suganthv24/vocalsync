from django.urls import path
from . import views

urlpatterns = [
    path('', views.index, name='index'),
    path('text-to-speech/', views.text_to_speech, name='text_to_speech'),
    path('speech-to-text/', views.speech_to_text, name='speech_to_text'),
    path('translate-text/', views.translate_text, name='translate_text'),
    path('download/<str:filename>/', views.download_audio, name='download_audio'),
    path('view-data/', views.view_data, name='view_data'),

]