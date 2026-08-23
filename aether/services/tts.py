"""Free Edge-TTS အဓိကထားပြီး အသံထုတ်လုပ်ရန်။"""

from __future__ import annotations

import asyncio
from pathlib import Path


VOICE_MAP = {
    "Myanmar Male": "my-MM-ThihaNeural",
    "Myanmar Female": "my-MM-NilarNeural",
    "English Male": "en-US-GuyNeural",
    "English Female": "en-US-JennyNeural",
}


async def _save_edge_tts(text: str, voice: str, output: Path, rate: str) -> None:
    import edge_tts
    communicator = edge_tts.Communicate(text=text, voice=VOICE_MAP.get(voice, voice), rate=rate)
    await communicator.save(str(output))


def synthesize(text: str, output: Path, voice: str = "Myanmar Male", rate: str = "+0%") -> Path:
    """Worker process အတွင်း async event-loop conflict မဖြစ်အောင် run ပါ။"""
    asyncio.run(_save_edge_tts(text, voice, output, rate))
    if not output.exists() or output.stat().st_size < 100:
        raise RuntimeError("TTS output is empty")
    return output
