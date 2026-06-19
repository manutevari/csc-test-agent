import io
import os
import re

import streamlit as st
from openai import OpenAI


DEVANAGARI_PATTERN = re.compile(r"[\u0900-\u097F]")
HINGLISH_HINT_PATTERN = re.compile(
    r"\b("
    r"kya|kaise|batao|bataiye|karo|karna|karun|hoga|hai|nahi|"
    r"yojana|kisan|panjikaran|sudhar|praman|seva|aavedan|"
    r"process|registration|status"
    r")\b",
    re.IGNORECASE,
)


def secret(name, default=""):
    try:
        value = st.secrets.get(name, None)
    except Exception:
        value = None

    if value:
        return str(value).strip()

    return os.getenv(name, default).strip()


def configured_secret(*names):
    for name in names:
        value = secret(name)
        placeholder = value.upper()
        if (
            value
            and not placeholder.startswith("YOUR_")
            and not placeholder.startswith("CHANGE_ME")
            and not placeholder.startswith("REPLACE_")
            and placeholder != "TODO"
        ):
            return value

    return ""


def normalize_voice_language(language_choice="Auto", sample_text=""):
    if language_choice == "Hindi":
        return "hi-IN"
    if language_choice == "English":
        return "en-IN"

    if DEVANAGARI_PATTERN.search(sample_text or "") or HINGLISH_HINT_PATTERN.search(sample_text or ""):
        return "hi-IN"

    return "en-IN"


def openai_audio_enabled():
    return bool(configured_secret("OPENAI_AUDIO_API_KEY", "OPENAI_API_KEY"))


def voice_stt_provider():
    return secret("VOICE_STT_PROVIDER", "browser").strip().lower()


def whisper_stt_enabled():
    return voice_stt_provider() in {"openai", "whisper"} and openai_audio_enabled()


def transcribe_with_whisper(audio_bytes, language_choice="Auto"):
    if not audio_bytes:
        return "", "No audio was captured. Please try again."

    api_key = configured_secret("OPENAI_AUDIO_API_KEY", "OPENAI_API_KEY")
    if not api_key:
        return "", "OpenAI audio transcription is not configured."

    client = OpenAI(api_key=api_key)
    audio_file = io.BytesIO(audio_bytes)
    audio_file.name = "csc_voice_input.wav"

    kwargs = {
        "model": secret("OPENAI_STT_MODEL", "whisper-1"),
        "file": audio_file,
        "prompt": "CSC services, Digital Seva, PM Kisan, PAN, DigiPay, Ayushman Bharat, e-Shram, Hindi and English.",
    }

    if language_choice == "Hindi":
        kwargs["language"] = "hi"
    elif language_choice == "English":
        kwargs["language"] = "en"

    try:
        response = client.audio.transcriptions.create(**kwargs)
    except Exception as exc:
        error_name = exc.__class__.__name__
        if "RateLimit" in error_name:
            return "", "Voice transcription is temporarily busy. Please try again in a moment, or use browser speech input."
        return "", "Voice transcription could not complete. Please try again or type your question."

    text = getattr(response, "text", "") or ""
    return text.strip(), ""


def synthesize_with_openai(text, language_choice="Auto"):
    clean_text = (text or "").strip()
    if not clean_text:
        return None, "There is no answer text to speak."

    api_key = configured_secret("OPENAI_AUDIO_API_KEY", "OPENAI_API_KEY")
    if not api_key:
        return None, "OpenAI text-to-speech is not configured."

    client = OpenAI(api_key=api_key)
    voice = secret("OPENAI_TTS_VOICE", "nova")
    model = secret("OPENAI_TTS_MODEL", "tts-1")

    try:
        response = client.audio.speech.create(
            model=model,
            voice=voice,
            input=clean_text[:4000],
            response_format="mp3",
        )
    except Exception as exc:
        error_name = exc.__class__.__name__
        if "RateLimit" in error_name:
            return None, "Voice service busy. Please try again in a few seconds."
        return None, "Voice playback could not complete. Please try again or use browser voice."

    if hasattr(response, "read"):
        return response.read(), ""
    if hasattr(response, "content"):
        return response.content, ""

    try:
        return bytes(response), ""
    except TypeError:
        return None, "Text-to-speech returned an unsupported audio response."
