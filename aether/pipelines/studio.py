"""Movie, Translation, Faceless, Epic, Veo နှင့် Lyria background pipelines။"""

from __future__ import annotations

import json
import re
import shutil
import time
from pathlib import Path
from typing import Callable

from ..config import FFMPEG_BINARY, settings
from ..jobs import Job, JobStore
from ..storage import job_directory
from ..services.gemini import GeminiService
from ..services.media import (
    concat_videos, create_preview, duration, extract_audio, fit_audio, image_to_video,
    quality_report, render_video, run, video_size,
)
from ..services.subtitles import (
    clean_ai_srt, distribute_text, narration_text, parse_srt, write_ass, write_srt,
)
from ..services.tts import synthesize


Progress = Callable[[int, str], None]


def _subtitle_canvas(video_path: Path, ratio: str) -> tuple[int, int]:
    """ASS subtitle layout အတွက် final render canvas resolution သတ်မှတ်ရန်။"""
    if "9:16" in ratio:
        return 720, 1280
    if "16:9" in ratio:
        return 1280, 720
    return video_size(video_path)


def _styled_ass(items: list, srt_path: Path, video_path: Path, payload: dict) -> Path:
    """SRT ကို download အတွက်ထားပြီး styled ASS ကို burn-in အတွက်ပြင်ရန်။"""
    width, height = _subtitle_canvas(video_path, payload.get("ratio", "Original"))
    return write_ass(
        items, srt_path.with_suffix(".ass"), width=width, height=height,
        style=payload.get("subtitle_style", {}),
    )


def _delivery_assets(output: Path, workdir: Path) -> tuple[Path, Path]:
    """GitHub Artifact ထဲ preview နှင့် technical QC report ထည့်ရန်။"""
    preview = create_preview(output, workdir / "preview.mp4")
    report = quality_report(output, workdir / "render_report.json")
    return preview, report


def _resolve_input(payload: dict, workdir: Path) -> Path:
    """Upload path သို့မဟုတ် URL မှ input video ရယူရန်။"""
    if payload.get("input_path"):
        source = Path(payload["input_path"])
        if not source.exists():
            raise FileNotFoundError(f"Input file not found: {source}")
        destination = workdir / ("input" + source.suffix.lower())
        shutil.copy2(source, destination)
        return destination
    if payload.get("video_url"):
        destination = workdir / "input.mp4"
        try:
            import yt_dlp
        except ImportError as exc:
            raise RuntimeError("yt-dlp is required for URL downloads") from exc
        options = {
            "outtmpl": str(destination), "format": "bv*[height<=1080]+ba/b[height<=1080]",
            "merge_output_format": "mp4", "noplaylist": True, "socket_timeout": 30,
        }
        with yt_dlp.YoutubeDL(options) as downloader:
            downloader.download([payload["video_url"]])
        return destination
    raise ValueError("input_path or video_url is required")


def _metadata(raw: str) -> tuple[str, str]:
    title = re.search(r"\[TITLE:\s*(.*?)\]", raw, re.I | re.S)
    tags = re.search(r"\[TAGS:\s*(.*?)\]", raw, re.I | re.S)
    return (
        title.group(1).strip() if title else "AETHER Video",
        tags.group(1).strip() if tags else "#aetherstudio #myanmar",
    )


def movie_dubbing(job: Job, store: JobStore, progress: Progress) -> dict:
    """Movie ကို analyze → Burmese SRT → TTS → safe render လုပ်ရန်။"""
    workdir = job_directory(job.project_id, job.id)
    payload = job.payload
    progress(5, "Preparing video")
    input_checkpoint = store.checkpoint(job.id, "input")
    if input_checkpoint and Path(input_checkpoint["path"]).exists():
        input_video = Path(input_checkpoint["path"]); video_seconds = float(input_checkpoint["duration"])
    else:
        input_video = _resolve_input(payload, workdir)
        video_seconds = duration(input_video)
        store.save_checkpoint(job.id, "input", {"path": str(input_video), "duration": video_seconds})
    store.ensure_not_cancelled(job.id)

    audio_path = workdir / "source_audio.mp3"
    if not audio_path.exists():
        extract_audio(input_video, audio_path)
    script_checkpoint = store.checkpoint(job.id, "script")
    if script_checkpoint and Path(script_checkpoint["srt"]).exists() and Path(script_checkpoint["script"]).exists():
        progress(20, "Resuming from saved script")
        srt_path = Path(script_checkpoint["srt"]); script_path = Path(script_checkpoint["script"])
        subtitles = parse_srt(srt_path.read_text(encoding="utf-8-sig"), video_seconds)
        title = script_checkpoint.get("title", "AETHER Video"); tags = script_checkpoint.get("tags", "")
    else:
        progress(20, "Analyzing scenes and writing Burmese script")
        prompt = f"""You are a professional Burmese movie localizer. Analyze this media and create an engaging
    Burmese narration in valid SRT format for a {video_seconds:.2f}-second video.
    Style: {payload.get('style', 'Natural and cinematic')}. Start with a strong hook.
    Keep every timestamp within the video duration. Output SRT only, followed by:
    [TITLE: Burmese viral title]\n[TAGS: relevant hashtags]"""
        source_for_ai = input_video if payload.get("mode") == "Original AI Story" else audio_path
        raw = GeminiService().generate_from_media(source_for_ai, prompt, task="text")
        title, tags = _metadata(raw)
        subtitles = parse_srt(clean_ai_srt(raw), video_seconds)
        srt_path = write_srt(subtitles, workdir / "subtitles.srt")
        script_path = workdir / "script.txt"
        script_path.write_text(narration_text(subtitles), encoding="utf-8")
        store.save_checkpoint(job.id, "script", {"srt": str(srt_path), "script": str(script_path), "title": title, "tags": tags})
    store.ensure_not_cancelled(job.id)

    voice_checkpoint = store.checkpoint(job.id, "voice")
    if voice_checkpoint and Path(voice_checkpoint["path"]).exists():
        progress(50, "Resuming from saved narration")
        fitted_voice = Path(voice_checkpoint["path"])
    else:
        progress(50, "Generating narration")
        tts_engine = payload.get("tts_engine", "Edge-TTS · Free")
        voice_suffix = ".wav" if tts_engine.startswith("Google") else ".mp3"
        raw_voice = synthesize(
            narration_text(subtitles), workdir / f"voice_raw{voice_suffix}",
            voice=payload.get("voice", "Myanmar Male"), rate=payload.get("voice_rate", "+0%"),
            engine=tts_engine, custom_voice_id=payload.get("tts_voice_id", ""),
        )
        fitted_voice = fit_audio(raw_voice, video_seconds, workdir / "voice_fitted.wav")
        store.save_checkpoint(job.id, "voice", {"path": str(fitted_voice)})
    store.ensure_not_cancelled(job.id)

    ass_path = _styled_ass(subtitles, srt_path, input_video, payload)
    progress(72, "Rendering master video")
    blur = payload.get("blur_box")
    blur_box = tuple(int(value) for value in blur) if blur else None
    output = render_video(
        input_video, fitted_voice, workdir / "final.mp4",
        subtitle_path=ass_path if payload.get("burn_subtitles", True) else None,
        ratio=payload.get("ratio", "9:16"), mirror=bool(payload.get("mirror")),
        color=bool(payload.get("color")), blur_box=blur_box,
        watermark=payload.get("watermark", ""),
    )
    progress(92, "Creating mobile preview and quality report")
    preview, report = _delivery_assets(output, workdir)
    progress(100, "Completed")
    return {"video": str(output), "preview": str(preview), "srt": str(srt_path),
            "ass": str(ass_path), "report": str(report), "script": str(script_path),
            "source_video": str(input_video), "audio": str(fitted_voice), "title": title, "tags": tags}


def translation(job: Job, store: JobStore, progress: Progress) -> dict:
    """မူရင်းအသံကို timestamp မပျက်ဘဲ target language သို့ပြန်ဆိုရန်။"""
    workdir = job_directory(job.project_id, job.id); payload = job.payload
    progress(5, "Preparing source media")
    input_checkpoint = store.checkpoint(job.id, "input")
    if input_checkpoint and Path(input_checkpoint["path"]).exists():
        input_video = Path(input_checkpoint["path"]); video_seconds = float(input_checkpoint["duration"])
    else:
        input_video = _resolve_input(payload, workdir); video_seconds = duration(input_video)
        store.save_checkpoint(job.id, "input", {"path": str(input_video), "duration": video_seconds})
    audio_path = workdir / "source_audio.mp3"
    if not audio_path.exists():
        extract_audio(input_video, audio_path)
    store.ensure_not_cancelled(job.id)
    translation_checkpoint = store.checkpoint(job.id, "translation")
    if translation_checkpoint and Path(translation_checkpoint["srt"]).exists():
        progress(25, "Resuming from saved translation")
        srt_path = Path(translation_checkpoint["srt"]); title = translation_checkpoint.get("title", "Localized Video")
    else:
        progress(25, "Transcribing and translating")
        prompt = f"""Listen to this audio and produce valid SRT translated into {payload.get('target_language', 'Myanmar')}.
    Preserve meaning, speaker tone and timing. Style: {payload.get('style', 'Natural conversational')}.
    Dictionary: {payload.get('dictionary', 'None')}. Keep all timestamps within {video_seconds:.2f} seconds.
    Output SRT only, followed by [TITLE: localized viral title]."""
        raw = GeminiService().generate_from_media(audio_path, prompt, task="text")
        title, _ = _metadata(raw)
        subtitles = parse_srt(clean_ai_srt(raw), video_seconds)
        srt_path = write_srt(subtitles, workdir / "translated.srt")
        store.save_checkpoint(job.id, "translation", {"srt": str(srt_path), "title": title})
    store.ensure_not_cancelled(job.id)
    subtitles = parse_srt(srt_path.read_text(encoding="utf-8-sig"), video_seconds)
    ass_path = _styled_ass(subtitles, srt_path, input_video, payload)
    progress(70, "Rendering translated video")
    output = render_video(
        input_video, audio_path, workdir / "final.mp4",
        subtitle_path=ass_path if payload.get("burn_subtitles", True) else None,
        ratio=payload.get("ratio", "Original"), mirror=bool(payload.get("mirror")),
        color=bool(payload.get("color")), watermark=payload.get("watermark", ""),
    )
    progress(92, "Creating mobile preview and quality report")
    preview, report = _delivery_assets(output, workdir)
    progress(100, "Completed")
    return {"video": str(output), "preview": str(preview), "srt": str(srt_path),
            "ass": str(ass_path), "report": str(report), "source_video": str(input_video),
            "audio": str(audio_path), "title": title}


def rerender(job: Job, store: JobStore, progress: Progress) -> dict:
    """SRT editor မှ ပြင်ထားသည့်စာတန်းကို AI call မထပ်ခေါ်ဘဲ render ပြန်လုပ်ရန်။"""
    workdir = job_directory(job.project_id, job.id); payload = job.payload
    input_video, audio_path = Path(payload["source_video"]), Path(payload["audio"])
    if not input_video.exists() or not audio_path.exists():
        raise FileNotFoundError("Source video/audio for re-render is missing")
    progress(20, "Validating edited subtitles")
    items = parse_srt(payload["srt_text"], duration(input_video))
    srt_path = write_srt(items, workdir / "edited.srt")
    ass_path = _styled_ass(items, srt_path, input_video, payload)
    store.ensure_not_cancelled(job.id)
    progress(55, "Rendering edited version")
    output = render_video(
        input_video, audio_path, workdir / "final.mp4", subtitle_path=ass_path,
        ratio=payload.get("ratio", "Original"), watermark=payload.get("watermark", ""),
    )
    progress(90, "Creating mobile preview and quality report")
    preview, report = _delivery_assets(output, workdir)
    progress(100, "Completed")
    return {"video": str(output), "preview": str(preview), "srt": str(srt_path),
            "ass": str(ass_path), "report": str(report),
            "source_video": str(input_video), "audio": str(audio_path)}


def _parse_json(raw: str) -> dict:
    match = re.search(r"\{[\s\S]*\}", raw)
    if not match:
        raise ValueError("AI response did not contain JSON")
    return json.loads(match.group(0))


def _story_video(job: Job, store: JobStore, progress: Progress, epic: bool = False) -> dict:
    """Faceless/Epic အတွက် scene-based images, narration နှင့် subtitles ဖန်တီးရန်။"""
    workdir = job_directory(job.project_id, job.id); payload = job.payload
    minutes = int(payload.get("duration_minutes", 2)); scene_count = max(4, min(20, minutes * 4))
    progress(10, "Writing story and scene plan")
    context = payload.get("character_bible", "") if epic else payload.get("niche", "Knowledge")
    prompt = f"""Create a highly engaging {'historical epic' if epic else 'faceless social video'} about:
    {payload.get('topic', 'an interesting mystery')}. Context: {context}.
    Write natural spoken Burmese with a 3-second hook and {scene_count} sequential scenes.
    Return valid JSON only: {{"title":"...","tags":"...","narration":"...",
    "scenes":[{{"visual_prompt":"English cinematic image prompt","text":"Burmese narration segment"}}]}}"""
    story_checkpoint = store.checkpoint(job.id, "story")
    if story_checkpoint and Path(story_checkpoint["path"]).exists():
        plan = story_checkpoint["plan"]
    else:
        plan = _parse_json(GeminiService().generate_text(prompt, task="reasoning" if epic else "text"))
    scenes = plan.get("scenes", [])
    if not scenes:
        raise ValueError("Story plan contained no scenes")
    narration = plan.get("narration") or " ".join(scene.get("text", "") for scene in scenes)
    script_path = workdir / "script.txt"
    if not script_path.exists():
        script_path.write_text(narration, encoding="utf-8")
    store.save_checkpoint(job.id, "story", {"path": str(script_path), "plan": plan})
    store.ensure_not_cancelled(job.id)

    progress(30, "Generating narration")
    tts_engine = payload.get("tts_engine", "Edge-TTS · Free")
    voice_suffix = ".wav" if tts_engine.startswith("Google") else ".mp3"
    audio_path = workdir / f"narration{voice_suffix}"
    if not audio_path.exists():
        synthesize(
            narration, audio_path, voice=payload.get("voice", "Myanmar Male"),
            rate=payload.get("voice_rate", "+0%"), engine=tts_engine,
            custom_voice_id=payload.get("tts_voice_id", ""),
        )
    total_seconds = duration(audio_path); each_seconds = total_seconds / len(scenes)
    ratio = payload.get("ratio", "9:16"); width, height = ((720, 1280) if "9:16" in ratio else (1280, 720))
    clips: list[Path] = []
    gemini = GeminiService()
    for index, scene in enumerate(scenes):
        store.ensure_not_cancelled(job.id)
        progress(35 + int(40 * (index + 1) / len(scenes)), f"Generating scene {index + 1}/{len(scenes)}")
        image = workdir / f"scene_{index:03d}.jpg"; clip = workdir / f"scene_{index:03d}.mp4"
        if not image.exists():
            gemini.generate_image(scene.get("visual_prompt", "cinematic Myanmar scene"), image, width, height)
        if not clip.exists():
            image_to_video(image, each_seconds, clip, width, height)
        clips.append(clip)
    silent_video = concat_videos(clips, workdir / "visuals.mp4")
    subtitles = distribute_text(narration, total_seconds)
    srt_path = write_srt(subtitles, workdir / "subtitles.srt")
    ass_path = _styled_ass(subtitles, srt_path, silent_video, payload)
    progress(82, "Rendering master video")
    output = render_video(
        silent_video, audio_path, workdir / "final.mp4",
        subtitle_path=ass_path if payload.get("burn_subtitles", True) else None,
        ratio=ratio, watermark=payload.get("watermark", ""),
    )
    progress(92, "Creating mobile preview and quality report")
    preview, report = _delivery_assets(output, workdir)
    progress(100, "Completed")
    return {"video": str(output), "preview": str(preview), "srt": str(srt_path),
            "ass": str(ass_path), "report": str(report), "script": str(script_path),
            "title": plan.get("title", "AETHER Story"), "tags": plan.get("tags", "")}


def faceless(job: Job, store: JobStore, progress: Progress) -> dict:
    return _story_video(job, store, progress, epic=False)


def epic(job: Job, store: JobStore, progress: Progress) -> dict:
    return _story_video(job, store, progress, epic=True)


def veo(job: Job, store: JobStore, progress: Progress) -> dict:
    """Google GenAI SDK ၏ Veo long-running operation ကို background မှာစောင့်ရန်။"""
    from google import genai
    from google.genai import types
    if not settings.gemini_keys:
        raise RuntimeError("GEMINI_API_KEY is not configured")
    workdir = job_directory(job.project_id, job.id); payload = job.payload
    client = genai.Client(api_key=settings.gemini_keys[0], http_options=types.HttpOptions(timeout=settings.api_timeout_seconds * 1000))
    progress(10, "Submitting Veo generation")
    operation = client.models.generate_videos(
        model=settings.models["video"], prompt=payload["prompt"],
        config=types.GenerateVideosConfig(number_of_videos=1),
    )
    deadline = time.monotonic() + 1800
    while not operation.done:
        store.ensure_not_cancelled(job.id)
        if time.monotonic() > deadline:
            raise TimeoutError("Veo generation timed out")
        progress(min(90, 15 + int((1800 - (deadline - time.monotonic())) / 24)), "Veo is generating video")
        time.sleep(10); operation = client.operations.get(operation)
    generated = operation.response.generated_videos[0].video
    output = workdir / "veo.mp4"
    client.files.download(file=generated); generated.save(str(output))
    progress(100, "Completed")
    return {"video": str(output)}


def lyria(job: Job, store: JobStore, progress: Progress) -> dict:
    """Lyria SDK method ရရှိသည့် environment တွင် music clip ဖန်တီးရန်။"""
    from google import genai
    if not settings.gemini_keys:
        raise RuntimeError("GEMINI_API_KEY is not configured")
    workdir = job_directory(job.project_id, job.id); client = genai.Client(api_key=settings.gemini_keys[0])
    if not hasattr(client.models, "generate_music"):
        raise RuntimeError("Installed google-genai SDK does not expose generate_music; upgrade the SDK")
    progress(15, "Generating music")
    response = client.models.generate_music(model=settings.models["music"], prompt=job.payload["prompt"])
    output = workdir / "music.wav"
    audio_data = getattr(response, "audio", None) or getattr(response, "data", None)
    if hasattr(audio_data, "save"):
        audio_data.save(str(output))
    elif isinstance(audio_data, bytes):
        output.write_bytes(audio_data)
    else:
        raise RuntimeError("Lyria response did not include audio data")
    progress(100, "Completed")
    return {"audio": str(output)}


PIPELINES = {
    "movie_dubbing": movie_dubbing,
    "translation": translation,
    "faceless": faceless,
    "epic": epic,
    "veo": veo,
    "lyria": lyria,
    "rerender": rerender,
}
