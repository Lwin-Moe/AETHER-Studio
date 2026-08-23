"""SRT parsing, validation နှင့် မြန်မာစာတန်း ASS styling utilities။"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path


@dataclass
class Subtitle:
    start: float
    end: float
    text: str


def parse_time(value: str) -> float:
    match = re.fullmatch(r"(\d{1,2}):(\d{2}):(\d{2})[,.](\d{1,3})", value.strip())
    if not match:
        raise ValueError(f"Invalid SRT time: {value}")
    h, m, s, ms = (int(part) for part in match.groups())
    return h * 3600 + m * 60 + s + ms / (10 ** len(match.group(4)))


def format_time(seconds: float) -> str:
    seconds = max(0, seconds)
    h = int(seconds // 3600); m = int(seconds % 3600 // 60)
    s = int(seconds % 60); ms = int(round((seconds % 1) * 1000))
    if ms == 1000:
        s += 1; ms = 0
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def clean_ai_srt(raw: str) -> str:
    raw = raw.replace("```srt", "").replace("```SRT", "").replace("```", "")
    return re.sub(r"\[TITLE:.*?\]|\[TAGS:.*?\]", "", raw, flags=re.I | re.S).strip()


def parse_srt(raw: str, video_duration: float | None = None) -> list[Subtitle]:
    """Malformed block ကိုတိတ်တိတ်မကျော်ဘဲ valid subtitle များသာပြန်ပေးရန်။"""
    items: list[Subtitle] = []
    pattern = re.compile(
        r"(?:^|\n)\s*\d+\s*\n\s*(\d{1,2}:\d{2}:\d{2}[,.]\d{1,3})\s*-->\s*"
        r"(\d{1,2}:\d{2}:\d{2}[,.]\d{1,3})\s*\n(.*?)(?=\n\s*\n|\Z)", re.S,
    )
    previous_end = 0.0
    for start_raw, end_raw, text in pattern.findall(clean_ai_srt(raw)):
        start, end = parse_time(start_raw), parse_time(end_raw)
        text = " ".join(text.split()).strip()
        if not text:
            continue
        start = max(start, previous_end)
        end = max(end, start + 0.35)
        if video_duration is not None:
            if start >= video_duration:
                break
            end = min(end, video_duration)
        if end > start:
            items.append(Subtitle(start, end, text))
            previous_end = end
    if not items:
        raise ValueError("Valid SRT blocks were not found")
    return items


def write_srt(items: list[Subtitle], path: Path) -> Path:
    body = "\n\n".join(
        f"{index}\n{format_time(item.start)} --> {format_time(item.end)}\n{item.text}"
        for index, item in enumerate(items, 1)
    )
    path.write_text(body + "\n", encoding="utf-8-sig")
    return path


def _ass_color(value: str, alpha: int = 0) -> str:
    """Web #RRGGBB အရောင်ကို ASS ၏ &HAABBGGRR format သို့ပြောင်းရန်။"""
    clean = value.strip().lstrip("#")
    if not re.fullmatch(r"[0-9a-fA-F]{6}", clean):
        clean = "FFFFFF"
    red, green, blue = clean[0:2], clean[2:4], clean[4:6]
    return f"&H{max(0, min(255, alpha)):02X}{blue}{green}{red}".upper()


def _ass_time(seconds: float) -> str:
    seconds = max(0.0, seconds)
    hours = int(seconds // 3600)
    minutes = int(seconds % 3600 // 60)
    secs = int(seconds % 60)
    centiseconds = int(round((seconds % 1) * 100))
    if centiseconds == 100:
        secs += 1
        centiseconds = 0
    return f"{hours}:{minutes:02d}:{secs:02d}.{centiseconds:02d}"


def write_ass(
    items: list[Subtitle],
    path: Path,
    *,
    width: int,
    height: int,
    style: dict | None = None,
) -> Path:
    """FFmpeg/libass တွင် font၊ color၊ outline နှင့် position မှန်ကန်စေရန် ASS ရေးရန်။"""
    style = style or {}
    position = str(style.get("position", "Bottom"))
    alignment = {"Top": 8, "Center": 5, "Bottom": 2}.get(position, 2)
    font = str(style.get("font", "Noto Sans Myanmar")).replace(",", " ")
    font_size = max(18, min(96, int(style.get("font_size", 44))))
    primary = _ass_color(str(style.get("font_color", "#FFFFFF")))
    outline_color = _ass_color(str(style.get("outline_color", "#000000")))
    background = bool(style.get("background", False))
    background_color = _ass_color(str(style.get("background_color", "#000000")), 96)
    outline = max(0, min(10, int(style.get("outline_width", 3))))
    shadow = max(0, min(10, int(style.get("shadow", 1))))
    margin_v = max(12, min(300, int(style.get("margin_v", 70))))
    border_style = 3 if background else 1
    effective_outline = max(8, outline * 2) if background else outline
    back_color = background_color if background else _ass_color("#000000", 128)

    header = f"""[Script Info]
ScriptType: v4.00+
PlayResX: {max(2, width)}
PlayResY: {max(2, height)}
ScaledBorderAndShadow: yes
WrapStyle: 0

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Aether,{font},{font_size},{primary},{primary},{outline_color},{back_color},-1,0,0,0,100,100,0,0,{border_style},{effective_outline},{shadow},{alignment},40,40,{margin_v},1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    lines = []
    for item in items:
        # ASS control characters မဖြစ်စေရန် escape လုပ်ပြီး မူရင်း line break ကိုထိန်းထားသည်။
        text = item.text.replace("\\", r"\\").replace("{", r"\{").replace("}", r"\}")
        text = text.replace("\n", r"\N")
        lines.append(
            f"Dialogue: 0,{_ass_time(item.start)},{_ass_time(item.end)},Aether,,0,0,0,,{text}"
        )
    path.write_text(header + "\n".join(lines) + "\n", encoding="utf-8-sig")
    return path


def narration_text(items: list[Subtitle]) -> str:
    return " ".join(item.text for item in items)


def distribute_text(text: str, total_seconds: float, max_chars: int = 42) -> list[Subtitle]:
    phrases = [p.strip() for p in re.split(r"(?<=[။.!?])\s+|\n+", text) if p.strip()]
    chunks: list[str] = []
    for phrase in phrases:
        while len(phrase) > max_chars:
            cut = phrase.rfind(" ", 0, max_chars)
            cut = cut if cut > 0 else max_chars
            chunks.append(phrase[:cut].strip()); phrase = phrase[cut:].strip()
        if phrase:
            chunks.append(phrase)
    chunks = chunks or [text.strip() or "..."]
    weights = [max(1, len(chunk)) for chunk in chunks]
    total_weight = sum(weights)
    cursor, items = 0.0, []
    for chunk, weight in zip(chunks, weights):
        end = min(total_seconds, cursor + total_seconds * weight / total_weight)
        items.append(Subtitle(cursor, max(cursor + 0.35, end), chunk)); cursor = end
    items[-1].end = total_seconds
    return items
