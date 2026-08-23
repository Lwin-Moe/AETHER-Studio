"""Project/job တစ်ခုစီအတွက် သီးခြားဖိုင်နေရာများ စီမံရန်။"""

from __future__ import annotations

import re
from pathlib import Path

from .config import DATA_DIR


def safe_name(name: str) -> str:
    return re.sub(r"[^a-zA-Z0-9._-]+", "_", name).strip("._") or "file"


def job_directory(project_id: str, job_id: str) -> Path:
    path = DATA_DIR / "projects" / safe_name(project_id) / "jobs" / safe_name(job_id)
    path.mkdir(parents=True, exist_ok=True)
    return path


def save_upload(uploaded_file, project_id: str) -> Path:
    """Streamlit upload ကို project-specific folder ထဲတွင် လုံခြုံစွာသိမ်းရန်။"""
    upload_dir = DATA_DIR / "projects" / safe_name(project_id) / "uploads"
    upload_dir.mkdir(parents=True, exist_ok=True)
    destination = upload_dir / safe_name(uploaded_file.name)
    destination.write_bytes(uploaded_file.getbuffer())
    return destination
