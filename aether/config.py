"""AETHER Studio ၏ ဗဟို configuration နှင့် AI model router။"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

try:
    from dotenv import load_dotenv
except ImportError:  # requirements မတင်ရသေးချိန် test/import လုပ်နိုင်ရန်
    def load_dotenv(*_args, **_kwargs):
        return False


ROOT_DIR = Path(__file__).resolve().parents[1]
load_dotenv(ROOT_DIR / ".env")
DATA_DIR = Path(os.getenv("AETHER_DATA_DIR", ROOT_DIR / "data")).resolve()
DATABASE_PATH = Path(os.getenv("AETHER_DATABASE_PATH", DATA_DIR / "aether.db")).resolve()
FFMPEG_BINARY = os.getenv("FFMPEG_BINARY", "ffmpeg")
FFPROBE_BINARY = os.getenv("FFPROBE_BINARY", "ffprobe")


MODEL_PRESETS = {
    "balanced": {
        "text": "gemini-3.7-flash",
        "reasoning": "gemini-3.1-pro-preview",
        "image": "gemini-3.1-flash-image",
        "tts": "gemini-3.1-flash-tts-preview",
        "video": "veo-3.1-fast-generate-preview",
        "music": "lyria-3-pro-preview",
    },
    "quality": {
        "text": "gemini-3.1-pro-preview",
        "reasoning": "gemini-3.1-pro-preview",
        "image": "gemini-3-pro-image",
        "tts": "gemini-2.5-pro-preview-tts",
        "video": "veo-3.1-generate-preview",
        "music": "lyria-3-pro-preview",
    },
    "economy": {
        "text": "gemini-3.1-flash-lite",
        "reasoning": "gemini-3.7-flash",
        "image": "gemini-3.1-flash-lite-image",
        "tts": "gemini-2.5-flash-preview-tts",
        "video": "veo-3.1-lite-generate-preview",
        "music": "lyria-3-clip-preview",
    },
}


@dataclass(frozen=True)
class Settings:
    """Worker နှင့် UI နှစ်ဖက်စလုံးက အသုံးပြုမည့် setting များ။"""

    model_profile: str = os.getenv("AETHER_MODEL_PROFILE", "balanced")
    api_timeout_seconds: int = int(os.getenv("AETHER_API_TIMEOUT", "600"))
    media_processing_timeout_seconds: int = int(os.getenv("AETHER_MEDIA_TIMEOUT", "300"))
    ffmpeg_timeout_seconds: int = int(os.getenv("AETHER_FFMPEG_TIMEOUT", "3600"))
    max_attempts: int = int(os.getenv("AETHER_MAX_ATTEMPTS", "3"))
    worker_poll_seconds: float = float(os.getenv("AETHER_WORKER_POLL", "2"))

    @property
    def models(self) -> dict[str, str]:
        return MODEL_PRESETS.get(self.model_profile, MODEL_PRESETS["balanced"])

    @property
    def gemini_keys(self) -> list[str]:
        raw = os.getenv("GEMINI_API_KEYS", os.getenv("GEMINI_API_KEY", ""))
        return [key.strip() for key in raw.split(",") if key.strip()]

    @property
    def groq_keys(self) -> list[str]:
        raw = os.getenv("GROQ_API_KEYS", os.getenv("GROQ_API_KEY", ""))
        return [key.strip() for key in raw.split(",") if key.strip()]


settings = Settings()
DATA_DIR.mkdir(parents=True, exist_ok=True)
