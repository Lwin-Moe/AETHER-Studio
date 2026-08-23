"""FFmpeg ကို timeout၊ error log နှင့် safe path များဖြင့် ခေါ်သုံးရန်။"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

from ..config import FFMPEG_BINARY, FFPROBE_BINARY, settings


class MediaError(RuntimeError):
    pass


def run(command: list[str], timeout: int | None = None) -> subprocess.CompletedProcess:
    try:
        return subprocess.run(
            command,
            capture_output=True,
            text=True,
            check=True,
            timeout=timeout or settings.ffmpeg_timeout_seconds,
        )
    except subprocess.TimeoutExpired as exc:
        raise MediaError(f"FFmpeg timeout after {exc.timeout} seconds") from exc
    except subprocess.CalledProcessError as exc:
        error = (exc.stderr or exc.stdout or str(exc))[-8000:]
        raise MediaError(error) from exc


def probe(path: Path) -> dict:
    result = run([
        FFPROBE_BINARY, "-v", "error", "-show_streams", "-show_format",
        "-of", "json", str(path),
    ], timeout=60)
    return json.loads(result.stdout)


def duration(path: Path) -> float:
    data = probe(path)
    return float(data.get("format", {}).get("duration", 0) or 0)


def video_size(path: Path) -> tuple[int, int]:
    for stream in probe(path).get("streams", []):
        if stream.get("codec_type") == "video":
            return int(stream["width"]), int(stream["height"])
    return 1280, 720


def extract_audio(video_path: Path, output_path: Path) -> Path:
    run([
        FFMPEG_BINARY, "-y", "-i", str(video_path), "-vn", "-ac", "1",
        "-ar", "16000", "-codec:a", "libmp3lame", "-q:a", "3", str(output_path),
    ])
    return output_path


def fit_audio(audio_path: Path, target_seconds: float, output_path: Path) -> Path:
    """အသံအရှည်ကို video အရှည်နှင့်ညီအောင် atempo + padding ဖြင့်ပြင်ရန်။"""
    audio_seconds = duration(audio_path)
    ratio = audio_seconds / max(target_seconds, 0.1)
    filters: list[str] = []
    while ratio > 2:
        filters.append("atempo=2")
        ratio /= 2
    while ratio < 0.5:
        filters.append("atempo=0.5")
        ratio /= 0.5
    if abs(ratio - 1) > 0.01:
        filters.append(f"atempo={ratio:.6f}")
    filters.append(f"apad=whole_dur={target_seconds:.3f}")
    run([
        FFMPEG_BINARY, "-y", "-i", str(audio_path), "-af", ",".join(filters),
        "-t", f"{target_seconds:.3f}", "-ar", "44100", str(output_path),
    ])
    return output_path


def render_video(
    input_video: Path,
    audio_path: Path,
    output_path: Path,
    *,
    subtitle_path: Path | None = None,
    ratio: str = "Original",
    mirror: bool = False,
    color: bool = False,
    blur_box: tuple[int, int, int, int] | None = None,
    watermark: str = "",
) -> Path:
    """Safe filter graph ဖြင့် video, subtitle, blur နှင့် audio ကိုပေါင်းရန်။"""
    source_w, source_h = video_size(input_video)
    target_w, target_h = source_w, source_h
    filters: list[str] = []
    if "9:16" in ratio:
        target_w, target_h = 720, 1280
        filters.append(f"scale={target_w}:{target_h}:force_original_aspect_ratio=increase")
        filters.append(f"crop={target_w}:{target_h}")
    elif "16:9" in ratio:
        target_w, target_h = 1280, 720
        filters.append(f"scale={target_w}:{target_h}:force_original_aspect_ratio=increase")
        filters.append(f"crop={target_w}:{target_h}")
    if mirror:
        filters.append("hflip")
    if color:
        filters.append("eq=brightness=0.01:contrast=1.04:saturation=1.05")

    simple_chain = ",".join(filters) if filters else "null"
    complex_parts = [f"[0:v]{simple_chain}[base]"]
    current = "base"

    if blur_box:
        x, y, w, h = blur_box
        x = max(0, min(int(x), target_w - 2)); y = max(0, min(int(y), target_h - 2))
        w = max(2, min(int(w), target_w - x)); h = max(2, min(int(h), target_h - y))
        complex_parts.extend([
            f"[{current}]split[clean][blur_source]",
            f"[blur_source]crop={w}:{h}:{x}:{y},gblur=sigma=20[blurred]",
            f"[clean][blurred]overlay={x}:{y}:eof_action=pass[with_blur]",
        ])
        current = "with_blur"

    if subtitle_path and subtitle_path.exists():
        escaped = str(subtitle_path.resolve()).replace("\\", "/").replace(":", "\\:").replace("'", "\\'")
        complex_parts.append(f"[{current}]subtitles='{escaped}'[with_subs]")
        current = "with_subs"

    if watermark:
        safe_text = watermark.replace("'", "\\'").replace(":", "\\:")
        complex_parts.append(
            f"[{current}]drawtext=text='{safe_text}':x=w-tw-24:y=24:fontsize=24:fontcolor=white@0.45[finalv]"
        )
        current = "finalv"

    run([
        FFMPEG_BINARY, "-y", "-i", str(input_video), "-i", str(audio_path),
        "-filter_complex", ";".join(complex_parts), "-map", f"[{current}]", "-map", "1:a:0",
        "-c:v", "libx264", "-preset", "veryfast", "-crf", "22", "-pix_fmt", "yuv420p",
        "-c:a", "aac", "-b:a", "160k", "-shortest", str(output_path),
    ])
    return output_path


def create_preview(input_path: Path, output_path: Path, width: int = 540) -> Path:
    """Dashboard review အတွက် CPU သက်သာပြီး file size သေးသော full-length preview ထုတ်ရန်။"""
    source_w, _ = video_size(input_path)
    filters: list[str] = []
    if source_w > width:
        filters.append(f"scale={width}:-2")
    command = [FFMPEG_BINARY, "-y", "-i", str(input_path)]
    if filters:
        command.extend(["-vf", ",".join(filters)])
    command.extend([
        "-c:v", "libx264", "-preset", "ultrafast", "-crf", "30",
        "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "80k",
        "-movflags", "+faststart", str(output_path),
    ])
    run(command)
    return output_path


def quality_report(video_path: Path, report_path: Path) -> Path:
    """Final output ကို browser-compatible ဖြစ်မဖြစ် lightweight technical QC စစ်ရန်။"""
    data = probe(video_path)
    streams = data.get("streams", [])
    video_stream = next((item for item in streams if item.get("codec_type") == "video"), {})
    audio_stream = next((item for item in streams if item.get("codec_type") == "audio"), {})
    seconds = float(data.get("format", {}).get("duration", 0) or 0)
    size_bytes = int(data.get("format", {}).get("size", 0) or video_path.stat().st_size)
    warnings: list[str] = []
    if not video_stream:
        warnings.append("Video stream မတွေ့ပါ။")
    if not audio_stream:
        warnings.append("Audio stream မတွေ့ပါ။")
    if seconds <= 0:
        warnings.append("Duration မမှန်ပါ။")
    if video_stream.get("codec_name") != "h264":
        warnings.append("Browser compatibility အတွက် H.264 codec မဟုတ်ပါ။")
    if video_stream.get("pix_fmt") != "yuv420p":
        warnings.append("Mobile compatibility အတွက် yuv420p pixel format မဟုတ်ပါ။")
    report = {
        "status": "PASS" if not warnings else "CHECK",
        "duration_seconds": round(seconds, 3),
        "size_mb": round(size_bytes / (1024 * 1024), 2),
        "resolution": f"{video_stream.get('width', 0)}x{video_stream.get('height', 0)}",
        "video_codec": video_stream.get("codec_name", "missing"),
        "pixel_format": video_stream.get("pix_fmt", "unknown"),
        "audio_codec": audio_stream.get("codec_name", "missing"),
        "warnings": warnings,
    }
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return report_path


def image_to_video(image_path: Path, seconds: float, output_path: Path, width: int, height: int) -> Path:
    frames = max(1, int(seconds * 25))
    vf = (
        f"scale={width}:{height}:force_original_aspect_ratio=increase,"
        f"crop={width}:{height},zoompan=z='min(zoom+0.001,1.12)':d={frames}:"
        f"x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':s={width}x{height},fps=25"
    )
    run([
        FFMPEG_BINARY, "-y", "-loop", "1", "-i", str(image_path), "-t", f"{seconds:.3f}",
        "-vf", vf, "-c:v", "libx264", "-pix_fmt", "yuv420p", "-an", str(output_path),
    ])
    return output_path


def concat_videos(paths: list[Path], output_path: Path) -> Path:
    concat_file = output_path.with_suffix(".concat.txt")
    concat_file.write_text("".join(f"file '{p.resolve()}'\n" for p in paths), encoding="utf-8")
    run([FFMPEG_BINARY, "-y", "-f", "concat", "-safe", "0", "-i", str(concat_file), "-c", "copy", str(output_path)])
    return output_path
