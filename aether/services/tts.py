"""Edge၊ Gemini Synergy၊ ElevenLabs နှင့် TTSMaker voice engine router။"""

from __future__ import annotations

import asyncio
import base64
import os
import wave
from pathlib import Path

import requests

from ..config import settings


EDGE_VOICES = {
    "ဇော်ဇော် · Male": "my-MM-ThihaNeural",
    "အောင်အောင် · Deep": "my-MM-ThihaNeural",
    "နှင်းနှင်း · Female": "my-MM-NilarNeural",
    "Myanmar Male": "my-MM-ThihaNeural",
    "Myanmar Female": "my-MM-NilarNeural",
}
GOOGLE_VOICES = {
    "Synergy Puck · Male": "Puck", "Synergy Aoede · Female": "Aoede",
    "Synergy Charon · Deep": "Charon", "Synergy Kore · Clear": "Kore",
}
ELEVEN_VOICES = {
    "Adam · Deep": "pNInz6obpgDQGcFmaJgB",
    "Rachel · Female": "21m00Tcm4TlvDq8ikWAM",
}


async def _save_edge_tts(text: str, voice: str, output: Path, rate: str) -> None:
    import edge_tts
    communicator = edge_tts.Communicate(text=text, voice=EDGE_VOICES.get(voice, voice), rate=rate)
    await communicator.save(str(output))


def _save_google_tts(text: str, voice: str, output: Path, rate: str) -> None:
    """Gemini 3.1 Flash TTS PCM response ကို standard 24 kHz WAV အဖြစ်သိမ်းရန်။"""
    from google import genai

    if not settings.gemini_keys:
        raise RuntimeError("Google Synergy TTS အတွက် GEMINI_API_KEYS မရှိပါ။")
    errors: list[str] = []
    voice_name = GOOGLE_VOICES.get(voice, voice)
    prompt = f"Read the following text exactly in a natural professional Burmese voice. Pace adjustment: {rate}.\n\n{text}"
    for key_index, api_key in enumerate(settings.gemini_keys):
        try:
            client = genai.Client(api_key=api_key)
            interaction = client.interactions.create(
                model=settings.models["tts"], input=prompt,
                response_format={"type": "audio"},
                generation_config={"speech_config": [{"voice": voice_name}]},
            )
            raw = interaction.output_audio.data
            pcm = base64.b64decode(raw) if isinstance(raw, str) else bytes(raw)
            with wave.open(str(output), "wb") as wav_file:
                wav_file.setnchannels(1); wav_file.setsampwidth(2); wav_file.setframerate(24000)
                wav_file.writeframes(pcm)
            return
        except Exception as exc:
            errors.append(f"key-{key_index + 1}: {exc}")
    raise RuntimeError("Google Synergy TTS failed: " + " | ".join(errors[-3:]))


def _save_elevenlabs(text: str, voice: str, output: Path, custom_voice_id: str = "") -> None:
    api_key = os.getenv("ELEVENLABS_API_KEY", "").strip()
    if not api_key:
        raise RuntimeError("ELEVENLABS_API_KEY ကို GitHub Actions Secret တွင်ထည့်ပါ။")
    voice_id = custom_voice_id.strip() or ELEVEN_VOICES.get(voice, voice)
    response = requests.post(
        f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}",
        params={"output_format": "mp3_44100_128"},
        headers={"xi-api-key": api_key, "Content-Type": "application/json"},
        json={"text": text, "model_id": "eleven_multilingual_v2"}, timeout=(30, 900),
    )
    if response.status_code != 200:
        raise RuntimeError(f"ElevenLabs API {response.status_code}: {response.text[:500]}")
    output.write_bytes(response.content)


def _save_ttsmaker(text: str, voice_id: str, output: Path, rate: str) -> None:
    api_key = os.getenv("TTSMAKER_API_KEY", "").strip()
    if not api_key:
        raise RuntimeError("TTSMAKER_API_KEY ကို GitHub Actions Secret တွင်ထည့်ပါ။")
    if not voice_id.strip().isdigit():
        raise RuntimeError("TTSMaker Voice ID ကို နံပါတ်ဖြင့်ထည့်ပါ။")
    speed = max(0.5, min(2.0, 1 + (int(rate.replace("%", "")) / 100)))
    response = requests.post(
        "https://api.ttsmaker.com/v2/create-tts-order",
        json={
            "api_key": api_key, "text": text, "voice_id": int(voice_id),
            "audio_format": "mp3", "audio_speed": speed, "audio_volume": 1,
            "audio_pitch": 1, "audio_high_quality": 1,
            "text_paragraph_pause_time": 300, "emotion_style_key": "", "emotion_intensity": 1,
        }, timeout=(30, 900),
    )
    if response.status_code != 200:
        raise RuntimeError(f"TTSMaker API {response.status_code}: {response.text[:500]}")
    data = response.json()
    if data.get("error_code") != 0 or not data.get("audio_download_url"):
        raise RuntimeError(f"TTSMaker failed: {data.get('error_summary') or data.get('msg')}")
    audio = requests.get(data["audio_download_url"], timeout=(30, 900)); audio.raise_for_status()
    output.write_bytes(audio.content)


def synthesize(
    text: str, output: Path, voice: str = "ဇော်ဇော် · Male", rate: str = "+0%",
    engine: str = "Edge-TTS · Free", custom_voice_id: str = "",
) -> Path:
    """ရွေးထားသော engine ကိုခေါ်ပြီး audio file အလွတ်မဖြစ်ကြောင်းစစ်ရန်။"""
    if engine.startswith("Google"):
        _save_google_tts(text, voice, output, rate)
    elif engine.startswith("ElevenLabs"):
        _save_elevenlabs(text, voice, output, custom_voice_id)
    elif engine.startswith("TTSMaker"):
        _save_ttsmaker(text, custom_voice_id, output, rate)
    else:
        asyncio.run(_save_edge_tts(text, voice, output, rate))
    if not output.exists() or output.stat().st_size < 100:
        raise RuntimeError(f"{engine} မှ audio output မရပါ။")
    return output
