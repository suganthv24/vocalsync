import os
import io
import uuid
import urllib.parse
import speech_recognition as sr
from pydub import AudioSegment
from gtts import gTTS
from deep_translator import GoogleTranslator
from django.shortcuts import render, redirect
from django.http import JsonResponse, FileResponse
from django.views.decorators.http import require_POST
from django.views.decorators.csrf import csrf_exempt
from django.utils.encoding import smart_str
from django.core.paginator import Paginator
from django.conf import settings
from .models import audio_data, text_data, translate_data
from .forms import RegisterForm
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required


# ----------- User Signup -----------
def signup_view(request):
    if request.method == 'POST':
        form = RegisterForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)  # Log the user in
            return redirect('index')
    else:
        form = RegisterForm()
    return render(request, 'myapp/signup.html', {'form': form})


# ----------- User Login -----------
def login_view(request):
    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')
        user = authenticate(username=username, password=password)
        if user:
            login(request, user)
            return redirect('index')
        else:
            return render(request, 'myapp/login.html', {'error': 'Invalid credentials'})
    return render(request, 'myapp/login.html')


# ----------- User Logout -----------
def logout_view(request):
    logout(request)
    return redirect('login')


# ----------- Home Page (Dashboard after login) -----------
@login_required(login_url='/login/')
def index(request):
    return render(request, 'myapp/index.html')  # You must create this template


# ----------- TTS Utility Function -----------
def speak_and_save(text, lang_code='en', speed=1.0):
    tts = gTTS(text=text, lang=lang_code)
    filename = f"{uuid.uuid4()}.mp3"
    filepath = os.path.join(settings.MEDIA_ROOT, filename)
    tts.save(filepath)
    if speed != 1.0:
        audio = AudioSegment.from_mp3(filepath)
        audio = audio.speedup(playback_speed=speed)
        audio.export(filepath, format="mp3")
    return filepath


# ----------- Text to Speech -----------
@csrf_exempt
@require_POST
def text_to_speech(request):
    try:
        text = request.POST.get('text', '')
        lang = request.POST.get('lang', 'en')
        speed = float(request.POST.get('speed', 1.0))

        tts = gTTS(text=text, lang=lang)
        filename = f"{uuid.uuid4()}.mp3"
        filepath = os.path.join(settings.MEDIA_ROOT, filename)
        tts.save(filepath)

        if speed != 1.0:
            audio = AudioSegment.from_mp3(filepath)
            audio = audio.speedup(playback_speed=speed)
            audio.export(filepath, format="mp3")

        language_dict = { "en": "English", "ta": "Tamil", "hi": "Hindi", "es": "Spanish", "fr": "French", "de": "German" }
        lang_name = language_dict.get(lang, lang)

        new_text = text.strip()[:15].replace(" ", "_")
        new_filename = f"{new_text}_{lang_name}.mp3"
        new_filename = urllib.parse.quote(new_filename)

        audio_data.insert_one({
            "user_id": request.user.id,
            "text": text,
            "filename": new_filename,
            "filepath": filepath,
            "lang_code": lang_name,
            "speed": speed,
        })

        return JsonResponse({
            'audio_url': f'/media/{filename}',
            'download_url': f'/download/{filename}'
        })
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


# ----------- Audio File Processor (MP3/WAV) -----------
def process_audio_file(audio_file):
    if audio_file.name.endswith('.mp3'):
        audio = AudioSegment.from_file(audio_file, format="mp3")
        wav_io = io.BytesIO()
        audio.export(wav_io, format="wav")
        wav_io.seek(0)
        return sr.AudioFile(wav_io)
    elif audio_file.name.endswith('.wav'):
        return sr.AudioFile(audio_file)
    else:
        raise ValueError('Unsupported file format.')


# ----------- Speech to Text -----------
@csrf_exempt
@require_POST
def speech_to_text(request):
    try:
        if 'audio' not in request.FILES:
            return JsonResponse({'error': 'No audio file provided'}, status=400)

        recognizer = sr.Recognizer()
        audio_file = request.FILES['audio']
        audio_source = process_audio_file(audio_file)

        with audio_source as source:
            audio_data_obj = recognizer.record(source)
            text = recognizer.recognize_google(audio_data_obj)

        text_data.insert_one({
            "user_id": request.user.id,
            "filename": audio_file.name,
            "text": text,
            "lang_code": 'English',
        })

        return JsonResponse({'text': text})
    except ValueError as e:
        return JsonResponse({'error': str(e)}, status=400)
    except sr.UnknownValueError:
        return JsonResponse({'error': 'Speech not recognized.'}, status=400)
    except sr.RequestError as e:
        return JsonResponse({'error': f'Service error: {str(e)}'}, status=503)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


# ----------- Translate Text -----------
@csrf_exempt
@require_POST
def translate_text(request):
    try:
        text = request.POST.get('text', '')
        target_lang = request.POST.get('target_lang', 'es')
        translated = GoogleTranslator(source='auto', target=target_lang).translate(text)

        language_dict = { "en": "English", "ta": "Tamil", "hi": "Hindi", "es": "Spanish", "fr": "French", "de": "German" }
        lang_name = language_dict.get(target_lang, target_lang)

        translate_data.insert_one({
            "user_id": request.user.id,
            "original_text": text,
            "translated_text": translated,
            "target_lang": lang_name,
        })

        return JsonResponse({'translated_text': translated})
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


# ----------- Download Audio File -----------
def download_audio(request, filename):
    filepath = os.path.join(settings.MEDIA_ROOT, filename)
    if not os.path.exists(filepath):
        return JsonResponse({'error': 'File not found'}, status=404)

    record = audio_data.find_one({"filename": filename})
    if not record:
        new_filename = f"VocalSync_Audio_{filename}"
    else:
        text = record.get('text', 'audio').strip()[:15].replace(" ", "_")
        lang = record.get('lang_code', 'unknown')
        new_filename = f"{text}_{lang}.mp3"

    new_filename = urllib.parse.quote(new_filename)
    response = FileResponse(open(filepath, 'rb'), as_attachment=True)
    response['Content-Disposition'] = f'attachment; filename="{smart_str(new_filename)}"'
    return response


# ----------- View All Stored Data (Secure) -----------
@login_required(login_url='/login/')
def view_data(request):
    search_query = request.GET.get('q', '').strip()
    user_id = request.user.id

    def filter_records(records, fields):
        if not search_query:
            return records
        return [r for r in records if any(search_query.lower() in str(r.get(f, '')).lower() for f in fields)]

    audio_records = filter_records(list(audio_data.find({"user_id": user_id})), ['filename', 'lang_code'])
    text_records = filter_records(list(text_data.find({"user_id": user_id})), ['filename', 'text'])
    translate_records = filter_records(list(translate_data.find({"user_id": user_id})), ['original_text', 'translated_text'])

    paginator = Paginator(audio_records + text_records + translate_records, 5)
    page_number = request.GET.get('page', 1)

    context = {
        'audio_data': paginator.get_page(page_number),
        'text_data': text_records,
        'translate_data': translate_records,
        'search_query': search_query
    }
    return render(request, 'myapp/view_data.html', context)
