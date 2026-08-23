"""Gemini key rotation, timeout, retry, media polling နှင့် fallback model service။"""

from __future__ import annotations

import random
import time
from pathlib import Path

from ..config import settings


class GeminiService:
    def __init__(self):
        if not settings.gemini_keys:
            raise RuntimeError("GEMINI_API_KEY or GEMINI_API_KEYS is not configured")

    def _client(self, key: str):
        from google import genai
        from google.genai import types
        return genai.Client(
            api_key=key,
            http_options=types.HttpOptions(timeout=settings.api_timeout_seconds * 1000),
        )

    def generate_text(self, prompt: str, task: str = "text", fallback_tasks: tuple[str, ...] = ("text",)) -> str:
        """Key နှင့် model နှစ်မျိုးလုံး auto-fallback လုပ်ရန်။"""
        model_tasks = (task,) + tuple(item for item in fallback_tasks if item != task)
        errors: list[str] = []
        for model_task in model_tasks:
            for model in settings.model_candidates(model_task):
                for key_index, key in enumerate(settings.gemini_keys):
                    for attempt in range(min(2, settings.max_attempts)):
                        try:
                            response = self._client(key).models.generate_content(model=model, contents=prompt)
                            text = (response.text or "").strip()
                            if not text:
                                raise RuntimeError("Gemini returned empty text")
                            return text
                        except Exception as exc:
                            errors.append(f"{model}/key-{key_index + 1}: {exc}")
                            if any(code in str(exc) for code in ("429", "503", "504", "timeout", "Timeout")):
                                time.sleep(min(12, (2 ** attempt) + random.random()))
                                continue
                            break
        raise RuntimeError("All Gemini attempts failed: " + " | ".join(errors[-4:]))

    def generate_from_media(self, media_path: Path, prompt: str, task: str = "text") -> str:
        """Media ကိုတစ်ခါ upload ပြီး key + stable model fallback ဖြင့်ခေါ်ရန်။"""
        errors: list[str] = []
        for key_index, key in enumerate(settings.gemini_keys):
            client = self._client(key)
            media_file = None
            try:
                media_file = client.files.upload(file=str(media_path))
                deadline = time.monotonic() + settings.media_processing_timeout_seconds
                while True:
                    current = client.files.get(name=media_file.name)
                    state = str(current.state)
                    if "PROCESSING" not in state:
                        if "FAILED" in state:
                            raise RuntimeError(f"Gemini media processing failed: {state}")
                        media_file = current
                        break
                    if time.monotonic() >= deadline:
                        raise TimeoutError("Gemini media processing timed out")
                    time.sleep(2)
                # Upload တစ်ခါတည်းကို model များစွာဖြင့်စမ်းပြီး 503 high-demand ကိုရှောင်သည်။
                for model in settings.model_candidates(task):
                    for attempt in range(min(2, settings.max_attempts)):
                        try:
                            response = client.models.generate_content(
                                model=model, contents=[media_file, prompt]
                            )
                            text = (response.text or "").strip()
                            if not text:
                                raise RuntimeError("Gemini returned empty text")
                            return text
                        except Exception as exc:
                            errors.append(f"{model}/key-{key_index + 1}: {exc}")
                            transient = any(
                                code in str(exc) for code in ("429", "503", "504", "timeout", "Timeout")
                            )
                            if transient and attempt == 0:
                                time.sleep(min(12, 2 + random.random() * 2))
                                continue
                            break
            except Exception as exc:
                errors.append(f"upload/key-{key_index + 1}: {exc}")
            finally:
                if media_file is not None:
                    try:
                        client.files.delete(name=media_file.name)
                    except Exception:
                        pass
        raise RuntimeError("Gemini media request failed after model/key fallbacks: " + " | ".join(errors[-8:]))

    def generate_image(self, prompt: str, output: Path, width: int = 720, height: int = 1280) -> Path:
        """Gemini image ကိုအရင်သုံးပြီး Pollinations ကို free fallback အဖြစ်ထားရန်။"""
        import requests
        for key in settings.gemini_keys:
            try:
                response = self._client(key).models.generate_content(
                    model=settings.models["image"], contents=prompt
                )
                for part in getattr(response, "parts", []) or []:
                    if getattr(part, "inline_data", None):
                        part.as_image().save(output)
                        if output.exists() and output.stat().st_size > 100:
                            return output
            except Exception:
                continue
        url = "https://image.pollinations.ai/prompt/" + requests.utils.quote(prompt)
        response = requests.get(url, params={"width": width, "height": height, "nologo": "true"}, timeout=(10, 90))
        response.raise_for_status()
        if "image" not in response.headers.get("Content-Type", ""):
            raise RuntimeError("Image provider did not return an image")
        output.write_bytes(response.content)
        return output
