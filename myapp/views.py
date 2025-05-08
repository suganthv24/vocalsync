import os
import io
import uuid
import speech_recognition as sr
from pydub import AudioSegment
from gtts import gTTS
from deep_translator import GoogleTranslator, exceptions
from django.shortcuts import render
from django.http import JsonResponse, FileResponse
from django.views.decorators.http import require_POST
from django.views.decorators.csrf import csrf_exempt
from django.conf import settings

def index(request):
    return render(request, "myapp/index.html")

def speak_and_save(text, lang_code='en', speed=1.0):
    """Generate and save audio from text, return the file path."""
    tts = gTTS(text=text, lang=lang_code)
    filename = f"{uuid.uuid4()}.mp3"
    filepath = os.path.join(settings.MEDIA_ROOT, filename)
    tts.save(filepath)
    
    if speed != 1.0:
        audio = AudioSegment.from_mp3(filepath)
        audio = audio.speedup(playback_speed=speed)
        audio.export(filepath, format="mp3")
    
    return filepath

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
            
        return JsonResponse({
            'audio_url': f'/media/{filename}',
            'download_url': f'/download/{filename}'
        })
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)
    

def process_audio_file(audio_file):
    """Convert audio file to WAV format for speech recognition."""
    file_name = audio_file.name
    if file_name.endswith('.mp3'):
        audio = AudioSegment.from_file(audio_file, format="mp3")
        wav_io = io.BytesIO()
        audio.export(wav_io, format="wav")
        wav_io.seek(0)
        return sr.AudioFile(wav_io)
    elif file_name.endswith('.wav'):
        return sr.AudioFile(audio_file)
    else:
        raise ValueError('Unsupported file format. Please upload WAV or MP3.')

@csrf_exempt
@require_POST
def speech_to_text(request):
    try:
        if 'audio' not in request.FILES:
            return JsonResponse({'error': 'No audio file provided'}, status=400)
        
        audio_file = request.FILES['audio']
        recognizer = sr.Recognizer()
        
        audio_source = process_audio_file(audio_file)
        with audio_source as source:
            audio_data = recognizer.record(source)
            text = recognizer.recognize_google(audio_data)

        return JsonResponse({'text': text})

    except ValueError as e:
        return JsonResponse({'error': str(e)}, status=400)
    except sr.UnknownValueError:
        return JsonResponse({'error': 'Speech not recognized, please try again.'}, status=400)
    except sr.RequestError as e:
        return JsonResponse({'error': f'Service unavailable: {str(e)}'}, status=503)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)

    except sr.UnknownValueError:
        return JsonResponse({'error': 'Speech not recognized, please try again.'}, status=400)
    except sr.RequestError as e:
        return JsonResponse({'error': f'Service unavailable: {str(e)}'}, status=503)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


@csrf_exempt
@require_POST
def translate_text(request):
    try:
        text = request.POST.get('text', '')
        target_lang = request.POST.get('target_lang', 'es')
        
        translated = GoogleTranslator(source='auto', target=target_lang).translate(text)
        return JsonResponse({'translated_text': translated})
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)
    
@csrf_exempt
@require_POST
def translate_audio(request):
    try:
        if 'audio' not in request.FILES:
            return JsonResponse({'error': 'No audio file provided'}, status=400)
        
        # Step 1: Convert Audio to Text
        audio_file = request.FILES['audio']
        file_name = audio_file.name
        recognizer = sr.Recognizer()

        # Process the audio file
        if file_name.endswith('.mp3'):
            audio = AudioSegment.from_file(audio_file, format="mp3")
            wav_io = io.BytesIO()
            audio.export(wav_io, format="wav")
            wav_io.seek(0)
            audio_source = sr.AudioFile(wav_io)

        elif file_name.endswith('.wav'):
            audio_source = sr.AudioFile(audio_file)

        else:
            return JsonResponse({'error': 'Unsupported file format. Please upload WAV or MP3.'}, status=400)

        # Recognize speech
        with audio_source as source:
            audio_data = recognizer.record(source)
            extracted_text = recognizer.recognize_google(audio_data)

        # Step 2: Translate Text
        target_lang = request.POST.get('target_lang', 'es')
        translated_text = GoogleTranslator(source='auto', target=target_lang).translate(extracted_text)

        # Step 3: Generate Translated Speech
        unique_filename = speak_and_save(translated_text, lang_code=target_lang)

        return JsonResponse({
            'audio_url': f'/media/{os.path.basename(unique_filename)}',
            'download_url': f'/download/{os.path.basename(unique_filename)}'
        })

    except sr.UnknownValueError:
        return JsonResponse({'error': 'Speech not recognized, please try again.'}, status=400)
    except sr.RequestError as e:
        return JsonResponse({'error': f'Service unavailable: {str(e)}'}, status=503)
    except exceptions.NotValidPayload:
        return JsonResponse({'error': 'Invalid payload for translation.'}, status=400)
    except Exception as e:
        # logger.error(f"Audio Translation Error: {str(e)}")
        return JsonResponse({'error': str(e)}, status=500)


def download_audio(request, filename):
    filepath = os.path.join(settings.MEDIA_ROOT, filename)
    if os.path.exists(filepath):
        return FileResponse(open(filepath, 'rb'), as_attachment=True)
    return JsonResponse({'error': 'File not found'}, status=404)