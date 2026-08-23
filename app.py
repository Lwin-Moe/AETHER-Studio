"""AETHER FILMWORKS GitHub Edition — Streamlit UI + GitHub Actions worker။"""

from __future__ import annotations

import hmac
import io
import json
import uuid
import zipfile
from pathlib import Path

import streamlit as st
from streamlit_autorefresh import st_autorefresh

from aether.config import MODEL_PRESETS
from aether.github_actions import GitHubActionsClient, GitHubSettings


st.set_page_config(page_title="AETHER Studio · GitHub Edition", page_icon="✦", layout="wide")


# ─────────────────────────────────────────────────────────────────────────────
# Clean & modern UI theme
# ─────────────────────────────────────────────────────────────────────────────
st.markdown(
    """
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&family=Noto+Sans+Myanmar:wght@400;500;600;700&display=swap');
    :root { --bg:#060910;--panel:#0e1420;--panel2:#121a29;--line:#253047;--muted:#9ba9c0;--purple:#8b5cf6;--cyan:#22d3ee; }
    .stApp { background:radial-gradient(circle at 58% -15%,#17213d 0%,var(--bg) 42%);color:#eef4ff; }
    html,body,[class*="css"] { font-family:'Inter','Noto Sans Myanmar',sans-serif; }
    header[data-testid="stHeader"] { background:rgba(6,9,16,.82);backdrop-filter:blur(16px);border-bottom:1px solid rgba(37,48,71,.5); }
    [data-testid="stSidebar"] { background:#080d16;border-right:1px solid var(--line); }
    [data-testid="stSidebarNav"] { display:none; }
    /* Streamlit version ပြောင်းလဲသော်လည်း label/caption စာသားများ မှောင်မသွားစေရန် */
    [data-testid="stWidgetLabel"] p,
    [data-testid="stMarkdownContainer"] p,
    [data-testid="stCaptionContainer"],
    [data-testid="stCaptionContainer"] p,
    [data-testid="stRadio"] label p,
    [data-testid="stFileUploader"] small,
    .stCheckbox label p { color:#b8c3d9!important;opacity:1!important; }
    [data-testid="stSidebar"] [data-testid="stMarkdownContainer"] p,
    [data-testid="stSidebar"] [data-testid="stMarkdownContainer"] h1,
    [data-testid="stSidebar"] [data-testid="stMarkdownContainer"] h2,
    [data-testid="stSidebar"] [data-testid="stMarkdownContainer"] strong,
    [data-testid="stSidebar"] [data-testid="stRadio"] label p { color:#dce5f5!important;opacity:1!important; }
    .brand-lockup { padding:12px 8px 22px; }.brand-lockup .mark { width:38px;height:38px;border-radius:12px;display:grid;place-items:center;
      background:linear-gradient(135deg,#8b5cf6,#2563eb);box-shadow:0 10px 30px rgba(99,102,241,.35);font-size:1.1rem;margin-bottom:14px; }
    .brand-lockup b { display:block;color:#f6f8ff;font-size:1.08rem;letter-spacing:.12em; }.brand-lockup small { color:#728199;font-size:.66rem;letter-spacing:.14em; }
    [data-testid="stSidebar"] [role="radiogroup"] label { padding:9px 11px;border-radius:11px;margin:3px 0;border:1px solid transparent; }
    [data-testid="stSidebar"] [role="radiogroup"] label:has(input:checked) { background:#121c2d;border-color:#263958; }
    .worker-chip { margin:10px 2px 18px;padding:9px 11px;border:1px solid #1f3e45;border-radius:11px;background:#0c1b20;color:#75e7d4;font-size:.72rem;font-weight:700; }
    .worker-chip i { display:inline-block;width:7px;height:7px;border-radius:99px;background:#34d399;box-shadow:0 0 12px #34d399;margin-right:7px; }
    /* Widget အားလုံးကို premium dark input ပုံစံတစ်မျိုးတည်းဖြစ်စေရန် */
    [data-baseweb="base-input"],[data-baseweb="input"],
    div[data-baseweb="select"]>div,[data-baseweb="textarea"],textarea {
      background:#111927!important;border-color:#2a3852!important;border-radius:12px!important;box-shadow:none!important; }
    input,textarea { color:#edf4ff!important;-webkit-text-fill-color:#edf4ff!important;caret-color:#22d3ee!important; }
    input::placeholder,textarea::placeholder { color:#66758c!important;-webkit-text-fill-color:#66758c!important;opacity:1!important; }
    div[data-baseweb="select"] span,
    div[data-baseweb="select"] input { color:#edf4ff!important;-webkit-text-fill-color:#edf4ff!important; }
    [data-testid="stFileUploaderDropzone"] { background:#0d1522!important;border:1px dashed #33435f!important;color:#dbe7f8!important; }
    [data-testid="stFileUploaderDropzone"] span,
    [data-testid="stFileUploaderDropzone"] small { color:#9eabc0!important;opacity:1!important; }
    .block-container { max-width:1260px;padding-top:2.4rem;padding-bottom:4rem; }
    h1,h2,h3 { letter-spacing:-.035em; }
    .hero { padding:30px 34px;border:1px solid #293652;border-radius:24px;
      background:linear-gradient(125deg,rgba(139,92,246,.18),rgba(34,211,238,.045) 70%);margin-bottom:22px;box-shadow:0 24px 80px rgba(0,0,0,.18); }
    .hero h1 { margin:0;font-size:2.2rem }.hero p { color:#aab6ca!important;margin:.55rem 0 0; }
    .studio-kicker { color:#69e4f5;font-size:.72rem;font-weight:800;letter-spacing:.16em;text-transform:uppercase;margin-bottom:8px; }
    .section-title { margin:8px 0 14px;padding-bottom:10px;border-bottom:1px solid #222e43; }
    .section-title b { color:#f4f7ff;font-size:1.02rem; }.section-title span { display:block;color:#8391a8;font-size:.76rem;margin-top:3px; }
    .flowbar { display:flex;gap:8px;flex-wrap:wrap;margin:-4px 0 18px; }
    .flowbar span { padding:7px 11px;border:1px solid #28354d;border-radius:999px;background:#0d1421;color:#9daac0;font-size:.72rem;font-weight:700; }
    .flowbar span:first-child { color:#79e7f5;border-color:#27536a;background:#0c202c; }
    .metric { padding:18px;border-radius:16px;border:1px solid var(--line);background:rgba(16,21,33,.86); }
    .metric small { color:var(--muted) }.metric strong { display:block;font-size:1.65rem;margin-top:5px; }
    .status { display:inline-block;font-size:.72rem;font-weight:800;letter-spacing:.08em;padding:5px 9px;border-radius:999px; }
    .queued { background:#273047;color:#c4cce0 }.in_progress { background:#173b60;color:#7dd3fc }
    .success { background:#123d32;color:#6ee7b7 }.failure,.timed_out { background:#4b1d29;color:#fda4af }
    .cancelled { background:#3c2d20;color:#fdba74 }
    div[data-testid="stForm"] { background:linear-gradient(145deg,rgba(15,22,35,.96),rgba(9,14,23,.98));border:1px solid #26334a!important;border-radius:22px!important;padding:26px 26px 18px!important;box-shadow:0 24px 70px rgba(0,0,0,.22); }
    .stButton>button,.stDownloadButton>button { border-radius:12px!important;min-height:44px;font-weight:750; }
    .stButton>button[kind="primary"] { min-height:52px;background:linear-gradient(100deg,#7957f5,#6d5df8 48%,#227bd8);border:0;box-shadow:0 12px 28px rgba(109,93,248,.28); }
    div[data-testid="stSegmentedControl"] button { border-color:#2b3850!important;background:#0e1624!important;color:#aebbd0!important; }
    div[data-testid="stSegmentedControl"] button[aria-pressed="true"] { background:#1d3150!important;color:#f4f8ff!important;border-color:#3e6491!important; }
    .preview-shell { padding:14px;border:1px solid #26354f;border-radius:16px;background:#090f19;margin-top:10px; }
    @media (max-width: 720px) {
      .block-container { padding:1.1rem .85rem 5rem; }
      .hero { padding:22px 20px;border-radius:18px; }.hero h1 { font-size:1.65rem; }
      div[data-testid="stForm"] { padding:18px 14px 12px!important;border-radius:17px!important; }
      .metric { padding:13px; }.metric strong { font-size:1.3rem; }
      [data-testid="stSidebar"] { min-width:255px; }
    }
    </style>
    """,
    unsafe_allow_html=True,
)


def secret(name: str, default: str = "") -> str:
    try:
        return str(st.secrets.get(name, default))
    except Exception:
        return default


def require_access() -> None:
    """Public Streamlit app ကို ခွင့်မရှိသူက Actions မတင်နိုင်အောင်ကာကွယ်ရန်။"""
    expected = secret("APP_PASSWORD")
    if not expected:
        st.error("APP_PASSWORD ကို Streamlit Secrets တွင်အရင်သတ်မှတ်ပါ။")
        st.stop()
    if st.session_state.get("authenticated"):
        return
    st.markdown("## ✦ AETHER Studio")
    entered = st.text_input("Studio password", type="password")
    if st.button("Unlock", type="primary"):
        if hmac.compare_digest(entered, expected):
            st.session_state.authenticated = True
            st.rerun()
        st.error("Password မမှန်ပါ။")
    st.stop()


def github_client() -> GitHubActionsClient:
    token, repository = secret("GITHUB_TOKEN"), secret("GITHUB_REPOSITORY")
    if not token or not repository:
        st.error("GITHUB_TOKEN နှင့် GITHUB_REPOSITORY ကို Streamlit Secrets တွင်သတ်မှတ်ပါ။")
        st.stop()
    return GitHubActionsClient(GitHubSettings(
        token=token, repository=repository,
        workflow=secret("GITHUB_WORKFLOW", "aether-worker.yml"),
        branch=secret("GITHUB_BRANCH", "main"),
    ))


require_access()
client = github_client()
MAX_UPLOAD_MB = 500

# GitHub free runner တွင်ရှိသော Noto fonts များကိုသာ default ထားပြီး font missing error ကာကွယ်သည်။
SUBTITLE_PRESETS = {
    "Clean White": {"font": "Noto Sans Myanmar", "font_size": 44, "font_color": "#FFFFFF", "outline_color": "#000000", "outline_width": 3, "shadow": 1, "position": "Bottom", "background": False, "background_color": "#000000", "margin_v": 70},
    "Gold Cinematic": {"font": "Noto Serif Myanmar", "font_size": 46, "font_color": "#FFD76A", "outline_color": "#160F02", "outline_width": 3, "shadow": 2, "position": "Bottom", "background": False, "background_color": "#000000", "margin_v": 74},
    "Shorts Bold": {"font": "Noto Sans Myanmar", "font_size": 54, "font_color": "#FFFFFF", "outline_color": "#111827", "outline_width": 5, "shadow": 1, "position": "Center", "background": False, "background_color": "#000000", "margin_v": 60},
    "Readable Box": {"font": "Noto Sans Myanmar", "font_size": 42, "font_color": "#FFFFFF", "outline_color": "#000000", "outline_width": 2, "shadow": 0, "position": "Bottom", "background": True, "background_color": "#000000", "margin_v": 64},
    "Padauk Classic": {"font": "Padauk", "font_size": 46, "font_color": "#FFFFFF", "outline_color": "#111111", "outline_width": 3, "shadow": 1, "position": "Bottom", "background": False, "background_color": "#000000", "margin_v": 72},
}


def hero(title: str, description: str) -> None:
    st.markdown(f'<div class="hero"><h1>{title}</h1><p>{description}</p></div>', unsafe_allow_html=True)


def run_state(run: dict) -> str:
    return run.get("conclusion") or run.get("status") or "queued"


def parse_run_name(value: str) -> tuple[str, str, str]:
    parts = [part.strip() for part in value.split("·")]
    if len(parts) >= 4 and parts[0] == "AETHER":
        return parts[1], parts[2], " · ".join(parts[3:])
    return "unknown", "", value


def submit_job(mode: str, title: str, payload: dict, uploaded_file=None) -> str:
    """Upload ရှိလျှင် draft release တင်ပြီးမှ workflow dispatch လုပ်ရန်။"""
    job_id = uuid.uuid4().hex
    release = asset = None
    try:
        if uploaded_file is not None:
            # Public repo commit history ထဲ video မဝင်စေရန် draft asset ကိုသာသုံးသည်။
            release = client.create_input_release(job_id)
            uploaded_file.seek(0)
            asset = client.upload_release_asset(
                release, uploaded_file.name, uploaded_file,
                uploaded_file.type or "application/octet-stream",
            )
            payload["input_filename"] = Path(uploaded_file.name).name
        client.dispatch(
            job_id=job_id, job_type=mode, title=title, payload=payload,
            input_release_id=release["id"] if release else None,
            input_asset_id=asset["id"] if asset else None,
        )
        return job_id
    except Exception:
        if release:
            try:
                client.delete_release(release["id"])
            except Exception:
                pass
        raise


def artifact_preview(artifact_id: int) -> tuple[bytes, str, dict]:
    """Artifact ZIP မှ preview MP4 နှင့် success/failure metadata ကိုတစ်ခါတည်းဖတ်ရန်။"""
    archive = client.download_artifact(artifact_id)
    with zipfile.ZipFile(io.BytesIO(archive)) as bundle:
        names = bundle.namelist()
        metadata_name = next((name for name in names if name.lower().endswith("metadata.json")), "")
        metadata = json.loads(bundle.read(metadata_name).decode("utf-8")) if metadata_name else {}
        preview_name = next((name for name in names if name.lower().endswith("preview.mp4")), "")
        if not preview_name:
            preview_name = next((name for name in names if name.lower().endswith("final.mp4")), "")
        if not preview_name:
            return b"", "", metadata
        data = bundle.read(preview_name)
    return data, Path(preview_name).name, metadata


def create_page() -> None:
    hero("Production Console", "Source ရွေး၊ creative direction သတ်မှတ်ပြီး production job ကို background worker ဆီပို့ပါ။")
    modes = {
        "movie_dubbing": "🎙️ Movie Dubbing", "translation": "🌍 Global Translation",
        "faceless": "👻 Faceless Channel", "epic": "📚 Epic Series",
        "veo": "🎥 Veo Video", "lyria": "🎵 Lyria Music",
    }

    mode_col, project_col = st.columns([1.55, 1], gap="large")
    mode = mode_col.selectbox("Production studio", list(modes), format_func=modes.get)
    project_id = project_col.text_input(
        "Project ID", value=st.session_state.setdefault("project_id", uuid.uuid4().hex[:10]),
        help="Job များကို project တစ်ခုအဖြစ်စုစည်းရန် ID ဖြစ်သည်။",
    )

    # Form အပြင်ထားမှ source ရွေးချိန်တွင် URL/Upload field ချက်ချင်းပြောင်းပေးနိုင်သည်။
    source = None
    if mode in {"movie_dubbing", "translation"}:
        source = st.segmented_control(
            "Source delivery",
            ["Upload video", "Paste video URL"],
            default="Upload video",
            key=f"source_delivery_{mode}",
        )

    tts_engine = "Edge-TTS · Free"
    if mode in {"movie_dubbing", "faceless", "epic"}:
        tts_engine = st.segmented_control(
            "Voice engine",
            ["Edge-TTS · Free", "Google Synergy · Gemini", "ElevenLabs · Premium", "TTSMaker · Pro API"],
            default="Edge-TTS · Free", key=f"tts_engine_{mode}",
        )

    subtitle_preset = "Clean White"
    if mode not in {"veo", "lyria"}:
        subtitle_preset = st.selectbox(
            "Subtitle design preset", list(SUBTITLE_PRESETS),
            key=f"subtitle_preset_{mode}",
            help="Preset ရွေးပြီး form အောက်ရှိ font/color settings ကိုလိုသလိုထပ်ပြင်နိုင်သည်။",
        )

    st.markdown(
        '<div class="flowbar"><span>01 · SOURCE</span><span>02 · CREATIVE</span>'
        '<span>03 · OUTPUT</span><span>04 · BACKGROUND RENDER</span></div>',
        unsafe_allow_html=True,
    )

    with st.form(f"github_job_form_{mode}", clear_on_submit=False):
        payload: dict = {"project_id": project_id}
        uploaded = None
        left, right = st.columns([1.35, 1], gap="large")

        with left:
            st.markdown('<div class="section-title"><b>Source & Creative Direction</b><span>Input media နဲ့ AI ရေးသားမည့်ပုံစံ</span></div>', unsafe_allow_html=True)
            title = st.text_input("Production title", value=modes[mode].split(" ", 1)[1] + " · New project")

            if mode in {"movie_dubbing", "translation"}:
                if source == "Upload video":
                    uploaded = st.file_uploader("Upload source video", type=["mp4", "webm", "mov", "m4v"])
                    st.caption("MP4 / MOV / WEBM · Streamlit ပြသသည့် file limit အတွင်း · worker ပြီးချိန် temporary source ကိုဖျက်မည်။")
                else:
                    payload["video_url"] = st.text_input(
                        "Public video URL",
                        placeholder="https://youtube.com/...  or  https://www.tiktok.com/...",
                        help="Login မလိုသော public YouTube, TikTok သို့မဟုတ် direct video URL ထည့်ပါ။",
                    )
                payload["rights_confirmed"] = st.checkbox(
                    "ဤ source ကို အသုံးပြု/ပြင်ဆင်ရန် ခွင့်ရှိကြောင်း အတည်ပြုသည်။",
                    help="Copyright detection ကိုရှောင်ရန်မဟုတ်ဘဲ မူပိုင်ခွင့်ရှိသော သို့မဟုတ် အသုံးပြုခွင့်ရ content အတွက်ဖြစ်သည်။",
                )

            if mode == "movie_dubbing":
                payload["mode"] = st.selectbox("Narrative treatment", ["Translate Original", "Original AI Story"])
                payload["style"] = st.selectbox("Script personality", ["Natural and cinematic", "Gen-Z / Slang", "Comedy", "Suspense"])
            elif mode == "translation":
                payload["target_language"] = st.selectbox("Target language", ["Myanmar", "English", "Thai", "Bahasa Indonesia"])
                payload["style"] = st.selectbox("Translation personality", ["Natural conversational", "Gen-Z / Slang", "Formal / Direct"])
                payload["dictionary"] = st.text_area("Term dictionary · optional", placeholder="Gojo=ဂိုဂျို\nOppa=အိုပါး", height=105)
            elif mode in {"faceless", "epic"}:
                payload["topic"] = st.text_area("Story brief / episode focus", height=150, placeholder="Audience၊ hook၊ story angle နဲ့ မဖြစ်မနေပါရမည့်အချက်များ...")
                if mode == "faceless":
                    payload["niche"] = st.selectbox("Channel niche", ["Horror", "Reddit Drama", "Dark Psychology", "Fun Facts", "Motivation", "Ancient History"])
                else:
                    payload["character_bible"] = st.text_area("Character bible", height=125, placeholder="Character name, appearance, personality, continuity rules...")
            else:
                payload["prompt"] = st.text_area("Generation brief", height=230, placeholder="Scene၊ mood၊ camera၊ lighting၊ sound နဲ့ visual details များရေးပါ...")

        with right:
            st.markdown('<div class="section-title"><b>Output Specification</b><span>Delivery format၊ narration နဲ့ branding</span></div>', unsafe_allow_html=True)
            if mode in {"movie_dubbing", "faceless", "epic"}:
                payload["tts_engine"] = tts_engine
                if tts_engine.startswith("Google"):
                    voice_options = ["Synergy Puck · Male", "Synergy Aoede · Female", "Synergy Charon · Deep", "Synergy Kore · Clear"]
                elif tts_engine.startswith("ElevenLabs"):
                    voice_options = ["Adam · Deep", "Rachel · Female", "Custom Voice ID"]
                elif tts_engine.startswith("TTSMaker"):
                    voice_options = ["TTSMaker custom voice"]
                else:
                    voice_options = ["ဇော်ဇော် · Male", "အောင်အောင် · Deep", "နှင်းနှင်း · Female"]
                payload["voice"] = st.selectbox("Narrator voice", voice_options)
                if tts_engine.startswith("ElevenLabs") and payload["voice"] == "Custom Voice ID":
                    payload["tts_voice_id"] = st.text_input("ElevenLabs Voice ID", placeholder="Your voice_id")
                elif tts_engine.startswith("TTSMaker"):
                    payload["tts_voice_id"] = st.text_input("TTSMaker Voice ID", placeholder="ဥပမာ 777")
                if tts_engine.startswith("Google"):
                    st.caption("ရှိပြီးသား GEMINI_API_KEYS ကိုအသုံးပြုမည်။")
                elif tts_engine.startswith("ElevenLabs"):
                    st.caption("GitHub Secret: ELEVENLABS_API_KEY လိုအပ်သည်။")
                elif tts_engine.startswith("TTSMaker"):
                    st.caption("GitHub Secret: TTSMAKER_API_KEY · Pro/Studio API plan လိုအပ်သည်။")
            if mode in {"movie_dubbing", "faceless", "epic"}:
                payload["voice_rate"] = st.select_slider("Voice pacing", ["-10%", "-5%", "+0%", "+5%", "+10%"], value="+0%")
            if mode in {"faceless", "epic"}:
                payload["duration_minutes"] = st.slider("Target duration · minutes", 1, 10, 2)

            if mode not in {"veo", "lyria"}:
                payload["ratio"] = st.selectbox("Master aspect ratio", ["9:16", "16:9", "Original"])
                payload["burn_subtitles"] = st.toggle("Burn subtitles into video", True)
                base_style = SUBTITLE_PRESETS[subtitle_preset]
                with st.expander("Subtitle Designer", expanded=True):
                    payload["subtitle_style"] = {
                        "preset": subtitle_preset,
                        "font": st.selectbox(
                            "Myanmar font",
                            ["Noto Sans Myanmar", "Noto Serif Myanmar", "Padauk", "Padauk Book", "Noto Sans", "Noto Serif"],
                            index=["Noto Sans Myanmar", "Noto Serif Myanmar", "Padauk", "Padauk Book", "Noto Sans", "Noto Serif"].index(base_style["font"]),
                        ),
                        "font_size": st.slider("Font size", 24, 76, int(base_style["font_size"]), 2),
                        "position": st.selectbox(
                            "Position", ["Bottom", "Center", "Top"],
                            index=["Bottom", "Center", "Top"].index(base_style["position"]),
                        ),
                        "font_color": st.color_picker("Text color", base_style["font_color"]),
                        "outline_color": st.color_picker("Outline color", base_style["outline_color"]),
                        "outline_width": st.slider("Outline width", 0, 8, int(base_style["outline_width"])),
                        "shadow": st.slider("Shadow", 0, 6, int(base_style["shadow"])),
                        "background": st.toggle("Readable background box", bool(base_style["background"])),
                        "background_color": st.color_picker("Background color", base_style["background_color"]),
                        "margin_v": st.slider("Vertical safe margin", 20, 180, int(base_style["margin_v"]), 5),
                    }
                payload["watermark"] = st.text_input("Watermark · optional", placeholder="@channelname")
                st.info("Final MP4 + mobile preview + SRT/ASS + quality report ကို Artifact ZIP အဖြစ် 14 ရက်သိမ်းမည်။")
            else:
                profile = secret("AETHER_MODEL_PROFILE", "balanced")
                model_key = "video" if mode == "veo" else "music"
                model_name = MODEL_PRESETS.get(profile, MODEL_PRESETS["balanced"])[model_key]
                st.text_input("Active generation model", value=model_name, disabled=True)
                st.info("Generation availability သည် API account access နဲ့ region ပေါ်မူတည်သည်။")

        st.divider()
        submitted = st.form_submit_button("Launch background production  →", type="primary", use_container_width=True)

    if submitted:
        if mode in {"movie_dubbing", "translation"}:
            if source == "Upload video" and uploaded is None:
                st.error("Video file တင်ပေးပါ။")
                return
            if uploaded is not None and uploaded.size > MAX_UPLOAD_MB * 1024 * 1024:
                st.error(f"Video file သည် {MAX_UPLOAD_MB} MB ထက်ကြီးနေပါသည်။ Compress သို့မဟုတ် အပိုင်းခွဲပြီးတင်ပါ။")
                return
            if source == "Paste video URL" and not payload.get("video_url", "").strip():
                st.error("Video URL ထည့်ပေးပါ။")
                return
            if not payload.get("rights_confirmed"):
                st.error("Source ကို အသုံးပြုခွင့်ရှိကြောင်း အတည်ပြုပေးပါ။")
                return
        if mode in {"faceless", "epic", "veo", "lyria"} and not str(payload.get("topic") or payload.get("prompt") or "").strip():
            st.error("Topic သို့မဟုတ် prompt ထည့်ပေးပါ။")
            return
        if mode in {"movie_dubbing", "faceless", "epic"} and (
            tts_engine.startswith("TTSMaker")
            or (tts_engine.startswith("ElevenLabs") and payload.get("voice") == "Custom Voice ID")
        ) and not payload.get("tts_voice_id", "").strip():
            st.error("ရွေးထားသော TTS engine အတွက် Voice ID ထည့်ပေးပါ။")
            return
        try:
            with st.spinner("GitHub background worker ဆီ task တင်နေပါသည်..."):
                job_id = submit_job(mode, title, payload, uploaded)
            st.success(f"Task တင်ပြီးပါပြီ · {job_id[:12]}")
            st.info("အခု browser သို့မဟုတ် ဖုန်းကိုပိတ်နိုင်ပါပြီ။ Dashboard ပြန်ဝင်လျှင် status မြင်ရမည်။")
        except Exception as exc:
            st.error(f"Task submit မအောင်မြင်ပါ: {exc}")


def dashboard_page() -> None:
    hero("GitHub Job Dashboard", "GitHub Actions ပေါ်ရှိ queued, running နဲ့ completed tasks များကို စီမံပါ။")
    try:
        runs = client.list_runs(75)
    except Exception as exc:
        st.error(f"GitHub jobs မဖတ်နိုင်ပါ: {exc}")
        return
    states = [run_state(run) for run in runs]
    # Download link ပြင်ဆင်နေချိန် page မပြတ်စေရန် active job ရှိမှသာ auto-refresh လုပ်သည်။
    if any(state in {"queued", "in_progress"} for state in states):
        st_autorefresh(interval=5000, key="github_runs_refresh")
    metrics = {
        "Queued": states.count("queued"), "Running": states.count("in_progress"),
        "Completed": states.count("success"), "Failed": sum(state in {"failure", "timed_out"} for state in states),
    }
    for column, (name, value) in zip(st.columns(4), metrics.items()):
        column.markdown(f'<div class="metric"><small>{name}</small><strong>{value}</strong></div>', unsafe_allow_html=True)
    st.write("")
    selected = st.segmented_control("Filter", ["ALL", "queued", "in_progress", "success", "failure"], default="ALL")
    for run in runs:
        state = run_state(run)
        if selected != "ALL" and not (selected == "failure" and state == "timed_out") and state != selected:
            continue
        job_type, job_id, title = parse_run_name(run.get("display_title") or run.get("name", "AETHER"))
        with st.container(border=True):
            c1, c2 = st.columns([5, 1])
            c1.markdown(f"### {title}\n`{job_type}` · `{job_id[:12]}`")
            c2.markdown(f'<span class="status {state}">{state.upper()}</span>', unsafe_allow_html=True)
            if state == "queued":
                st.progress(0.05, text="Waiting for GitHub runner")
            elif state == "in_progress":
                st.progress(0.55, text="Background processing on GitHub")
            elif state == "success":
                st.progress(1.0, text="Completed")
            elif state in {"failure", "timed_out", "cancelled"}:
                st.error(f"Job {state}. Error metadata may be available below.")
            action_col, cancel_col = st.columns([3, 2])
            action_col.link_button("Open GitHub run logs", run["html_url"], use_container_width=True)
            if state in {"queued", "in_progress"}:
                if cancel_col.button("Cancel job", key=f"cancel_{run['id']}", use_container_width=True):
                    try:
                        client.cancel_run(run["id"])
                        st.toast("Cancel request ပို့ပြီးပါပြီ။")
                        st.rerun()
                    except Exception as exc:
                        st.error(f"Job cancel မအောင်မြင်ပါ: {exc}")
            elif state in {"failure", "timed_out", "cancelled"}:
                if cancel_col.button("Retry same job", key=f"retry_{run['id']}", use_container_width=True):
                    try:
                        client.rerun(run["id"])
                        st.toast("မူလ settings အတိုင်း job ပြန်တင်ပြီးပါပြီ။")
                        st.rerun()
                    except Exception as exc:
                        st.error(f"Job retry မအောင်မြင်ပါ: {exc}")
            if state in {"success", "failure", "timed_out", "cancelled"}:
                try:
                    artifacts = client.list_artifacts(run["id"])
                except Exception as exc:
                    st.warning(f"Artifacts မဖတ်နိုင်ပါ: {exc}")
                    artifacts = []
                for artifact in artifacts:
                    # Widget state နှင့် URL value ကို key တစ်ခုတည်းမသုံးရ။ Streamlit က
                    # widget ဖန်တီးပြီးနောက် ထို key ကိုပြင်ခွင့်မပေးသောကြောင့် သီးခြားခွဲထားသည်။
                    generate_key = f"generate_artifact_link_{artifact['id']}"
                    link_state_key = f"artifact_download_url_{artifact['id']}"
                    preview_key = f"artifact_preview_{artifact['id']}"
                    size_mb = float(artifact.get("size_in_bytes", 0)) / (1024 * 1024)
                    st.caption(f"{artifact['name']} · {size_mb:.1f} MB")
                    preview_col, zip_col = st.columns(2)
                    preview_label = "▶ Load video preview" if state == "success" else "View worker error details"
                    if preview_col.button(preview_label, key=f"load_{preview_key}", use_container_width=True):
                        try:
                            with st.spinner("Preview ကို Artifact မှဖတ်နေပါသည်..."):
                                preview_bytes, preview_name, preview_metadata = artifact_preview(int(artifact["id"]))
                                st.session_state[preview_key] = {
                                    "bytes": preview_bytes, "name": preview_name,
                                    "metadata": preview_metadata,
                                }
                        except Exception as exc:
                            st.error(f"Preview မဖွင့်နိုင်ပါ: {exc}")
                    preview_data = st.session_state.get(preview_key)
                    if preview_data:
                        preview_metadata = preview_data.get("metadata", {})
                        if preview_metadata.get("status") == "FAILED":
                            st.error(f"Worker error: {preview_metadata.get('error', 'Unknown error')}")
                            traceback_text = str(preview_metadata.get("traceback", "")).strip()
                            if traceback_text:
                                with st.expander("Technical traceback"):
                                    st.code(traceback_text, language="text")
                        elif preview_metadata.get("status") == "COMPLETED":
                            st.success("Worker metadata: completed")
                        if preview_data.get("bytes"):
                            st.markdown('<div class="preview-shell">', unsafe_allow_html=True)
                            st.video(preview_data["bytes"], format="video/mp4")
                            st.download_button(
                                "Download preview MP4  ↓", data=preview_data["bytes"],
                                file_name=preview_data["name"], mime="video/mp4",
                                key=f"download_{preview_key}", use_container_width=True,
                            )
                            st.markdown("</div>", unsafe_allow_html=True)
                        elif preview_metadata.get("status") != "FAILED":
                            st.warning("Artifact ထဲတွင် preview/final MP4 မတွေ့ပါ။")
                    if zip_col.button("Generate ZIP download", key=generate_key, use_container_width=True):
                        try:
                            with st.spinner("GitHub download link ပြင်ဆင်နေပါသည်..."):
                                # Client file အဟောင်းရှိနေလည်း app.py တစ်ဖိုင်တည်း update ဖြင့်
                                # GitHub temporary artifact URL ကိုရယူနိုင်ရန် inline request သုံးသည်။
                                response = client.session.get(
                                    client._url(f"/actions/artifacts/{artifact['id']}/zip"),
                                    timeout=30, allow_redirects=False,
                                )
                                client._check(response, (302,))
                                location = response.headers.get("Location", "")
                                if not location:
                                    raise RuntimeError("GitHub download URL မရပါ။")
                                st.session_state[link_state_key] = location
                        except Exception as exc:
                            st.error(f"Download link မရပါ: {exc}")
                    if st.session_state.get(link_state_key):
                        st.link_button(
                            "Download output ZIP  ↓", st.session_state[link_state_key],
                            use_container_width=True,
                        )
                        st.caption("Temporary link ဖြစ်သောကြောင့် မရတော့လျှင် Generate ကိုထပ်နှိပ်ပါ။")
    if not runs:
        st.info("GitHub background jobs မရှိသေးပါ။")


def settings_page() -> None:
    hero("Connection & Models", "Public repository connection၊ security နဲ့ active model profile ကိုစစ်ပါ။")
    st.success(f"Connected repository: {client.config.repository}")
    st.write(f"Workflow: `{client.config.workflow}` · Branch: `{client.config.branch}`")
    profile = secret("AETHER_MODEL_PROFILE", "balanced")
    st.json({"profile": profile, **MODEL_PRESETS.get(profile, MODEL_PRESETS["balanced"])})
    st.warning("Public app ဖြစ်သောကြောင့် APP_PASSWORD ကို မဖယ်ပါနှင့်။ Phone uploads များသည် temporary draft assets ဖြစ်သော်လည်း အလွန်အရေးကြီးသော private media မတင်သင့်ပါ။")


with st.sidebar:
    st.markdown(
        '<div class="brand-lockup"><div class="mark">✦</div><b>AETHER</b>'
        '<small>AUTONOMOUS MEDIA OS · BUILD 55.4 PRO</small></div>', unsafe_allow_html=True,
    )
    nav_labels = {"Dashboard": "◫  Operations", "Create Studio": "✦  Production", "Settings": "⚙  System"}
    page = st.radio("Workspace", list(nav_labels), format_func=nav_labels.get, label_visibility="collapsed")
    st.divider()
    st.markdown('<div class="worker-chip"><i></i>GITHUB WORKER READY</div>', unsafe_allow_html=True)
    st.caption("Detached processing · Safe to close")
    if st.button("Lock workspace", use_container_width=True):
        st.session_state.authenticated = False
        st.rerun()

if page == "Dashboard":
    dashboard_page()
elif page == "Settings":
    settings_page()
else:
    create_page()
