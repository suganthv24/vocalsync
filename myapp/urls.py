from django.urls import path
from . import views
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    path('', views.index, name='index'),

    # Core Features
    path('text-to-speech/', views.text_to_speech, name='text_to_speech'),
    path('speech-to-text/', views.speech_to_text, name='speech_to_text'),
    path('translate-text/', views.translate_text, name='translate_text'),
    path('download/<str:filename>/', views.download_audio, name='download_audio'),

    # Data Viewing (Login Required)
    path('view-data/', views.view_data, name='view_data'),

    # Authentication
    path('signup/', views.signup_view, name='signup'),
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
]

# Serve media files during development
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
