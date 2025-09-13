# -*- coding: utf-8 -*-
import io
from gtts import gTTS
import pygame

def tts_and_play(message: str, lang: str = "en"):
    try:
        tts = gTTS(text=message, lang=lang)
        audio_stream = io.BytesIO()
        tts.write_to_fp(audio_stream)
        audio_stream.seek(0)
        if not pygame.mixer.get_init():
            pygame.mixer.init()
        pygame.mixer.music.load(audio_stream, "mp3")
        pygame.mixer.music.play()
    except Exception as e:
        print(f"❌ TTS error: {e}")
