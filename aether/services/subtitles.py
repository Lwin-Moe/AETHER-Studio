"""SRT parsing, validation နှင့် စာကြောင်းအရှည်ပြုပြင်ခြင်း။"""

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
