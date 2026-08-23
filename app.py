"""AETHER FILMWORKS GitHub Edition — Streamlit UI + GitHub Actions worker။"""

from __future__ import annotations

import hmac
import uuid
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
    :root { --bg:#080b12;--panel:#101521;--line:#222a3b;--muted:#929db2;--purple:#7c5cff;--cyan:#38bdf8; }
    .stApp { background:radial-gradient(circle at 52% -20%,#1a2140 0%,var(--bg) 43%);color:#eef2ff; }
    html,body,[class*="css"] { font-family:'Inter','Noto Sans Myanmar',sans-serif; }
    [data-testid="stSidebar"] { background:#0b0f18;border-right:1px solid var(--line); }
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
    /* Light widget background ပေါ်တွင် input value ကိုဖတ်ရှုရလွယ်စေရန် */
    input,textarea { color:#172033!important;-webkit-text-fill-color:#172033!important; }
    input::placeholder,textarea::placeholder { color:#667085!important;-webkit-text-fill-color:#667085!important;opacity:1!important; }
    div[data-baseweb="select"] span,
    div[data-baseweb="select"] input { color:#172033!important;-webkit-text-fill-color:#172033!important; }
    [data-testid="stFileUploaderDropzone"] { color:#263247!important; }
    [data-testid="stFileUploaderDropzone"] span,
    [data-testid="stFileUploaderDropzone"] small { color:#596579!important;opacity:1!important; }
    .block-container { max-width:1440px;padding-top:2rem; }
    h1,h2,h3 { letter-spacing:-.035em; }
    .hero { padding:26px 30px;border:1px solid var(--line);border-radius:22px;
      background:linear-gradient(135deg,rgba(124,92,255,.18),rgba(56,189,248,.06));margin-bottom:20px; }
    .hero h1 { margin:0;font-size:2.25rem }.hero p { color:var(--muted);margin:.5rem 0 0; }
    .metric { padding:18px;border-radius:16px;border:1px solid var(--line);background:rgba(16,21,33,.86); }
    .metric small { color:var(--muted) }.metric strong { display:block;font-size:1.65rem;margin-top:5px; }
    .status { display:inline-block;font-size:.72rem;font-weight:800;letter-spacing:.08em;padding:5px 9px;border-radius:999px; }
    .queued { background:#273047;color:#c4cce0 }.in_progress { background:#173b60;color:#7dd3fc }
    .success { background:#123d32;color:#6ee7b7 }.failure,.timed_out { background:#4b1d29;color:#fda4af }
    .cancelled { background:#3c2d20;color:#fdba74 }
    .stButton>button,.stDownloadButton>button { border-radius:12px!important;min-height:44px;font-weight:700; }
    .stButton>button[kind="primary"] { background:linear-gradient(135deg,#6750f5,#8b5cf6);border:0; }
    div[data-baseweb="input"]>div,div[data-baseweb="select"]>div,textarea {
      background:#111827!important;border-color:#293249!important;border-radius:12px!important; }
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


def create_page() -> None:
    hero("Create Background Job", "Task တင်ပြီးသည်နှင့် GitHub Actions က ဆက်လုပ်မည်။ Browser သို့မဟုတ် ဖုန်းပိတ်နိုင်ပါသည်။")
    modes = {
        "movie_dubbing": "🎙️ Movie Dubbing", "translation": "🌍 Global Translation",
        "faceless": "👻 Faceless Channel", "epic": "📚 Epic Series",
        "veo": "🎥 Veo Video", "lyria": "🎵 Lyria Music",
    }
    mode = st.selectbox("Studio mode", list(modes), format_func=modes.get)
    project_id = st.text_input("Project ID", value=st.session_state.setdefault("project_id", uuid.uuid4().hex[:10]))

    with st.form("github_job_form", clear_on_submit=False):
        title = st.text_input("Task title", value=modes[mode].split(" ", 1)[1] + " project")
        payload: dict = {"project_id": project_id}
        uploaded = None

        if mode in {"movie_dubbing", "translation"}:
            source = st.radio("Video source", ["Phone / Computer Upload", "Public Video URL"], horizontal=True)
            if source == "Phone / Computer Upload":
                uploaded = st.file_uploader("MP4 / WEBM / MOV", type=["mp4", "webm", "mov", "m4v"])
                st.caption(f"အများဆုံး {MAX_UPLOAD_MB} MB · GitHub draft release တွင်ယာယီထားပြီး worker ပြီးချိန် ဖျက်မည်။")
            else:
                payload["video_url"] = st.text_input("Video URL")

        if mode == "movie_dubbing":
            payload["mode"] = st.selectbox("Recap mode", ["Translate Original", "Original AI Story"])
            payload["style"] = st.selectbox("Script style", ["Natural and cinematic", "Gen-Z / Slang", "Comedy", "Suspense"])
            payload["voice"] = st.selectbox("Narrator voice", ["Myanmar Male", "Myanmar Female"])
            payload["voice_rate"] = st.select_slider("Voice speed", ["-10%", "-5%", "+0%", "+5%", "+10%"], value="+0%")
        elif mode == "translation":
            payload["target_language"] = st.selectbox("Target language", ["Myanmar", "English", "Thai", "Bahasa Indonesia"])
            payload["style"] = st.selectbox("Translation style", ["Natural conversational", "Gen-Z / Slang", "Formal / Direct"])
            payload["dictionary"] = st.text_area("Custom dictionary", placeholder="Gojo=ဂိုဂျို\nOppa=အိုပါး")
        elif mode in {"faceless", "epic"}:
            payload["topic"] = st.text_area("Topic / Episode focus", height=120)
            if mode == "faceless":
                payload["niche"] = st.selectbox("Niche", ["Horror", "Reddit Drama", "Dark Psychology", "Fun Facts", "Motivation", "Ancient History"])
            else:
                payload["character_bible"] = st.text_area("Character Bible", height=150)
            payload["duration_minutes"] = st.slider("Duration (minutes)", 1, 10, 2)
            payload["voice"] = st.selectbox("Narrator voice", ["Myanmar Male", "Myanmar Female"])
        else:
            payload["prompt"] = st.text_area("Generation prompt", height=160)

        if mode not in {"veo", "lyria"}:
            c1, c2, c3 = st.columns(3)
            payload["ratio"] = c1.selectbox("Ratio", ["9:16", "16:9", "Original"])
            payload["burn_subtitles"] = c2.checkbox("Burn subtitles", True)
            payload["watermark"] = c3.text_input("Watermark")

        submitted = st.form_submit_button("Start background job", type="primary", use_container_width=True)

    if submitted:
        if mode in {"movie_dubbing", "translation"}:
            if source == "Phone / Computer Upload" and uploaded is None:
                st.error("Video file တင်ပေးပါ။")
                return
            if uploaded is not None and uploaded.size > MAX_UPLOAD_MB * 1024 * 1024:
                st.error(f"Video file သည် {MAX_UPLOAD_MB} MB ထက်ကြီးနေပါသည်။ Compress သို့မဟုတ် အပိုင်းခွဲပြီးတင်ပါ။")
                return
            if source == "Public Video URL" and not payload.get("video_url", "").strip():
                st.error("Video URL ထည့်ပေးပါ။")
                return
        if mode in {"faceless", "epic", "veo", "lyria"} and not str(payload.get("topic") or payload.get("prompt") or "").strip():
            st.error("Topic သို့မဟုတ် prompt ထည့်ပေးပါ။")
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
    st_autorefresh(interval=5000, key="github_runs_refresh")
    try:
        runs = client.list_runs(75)
    except Exception as exc:
        st.error(f"GitHub jobs မဖတ်နိုင်ပါ: {exc}")
        return
    states = [run_state(run) for run in runs]
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
            if state in {"success", "failure", "timed_out", "cancelled"}:
                try:
                    artifacts = client.list_artifacts(run["id"])
                except Exception as exc:
                    st.warning(f"Artifacts မဖတ်နိုင်ပါ: {exc}")
                    artifacts = []
                for artifact in artifacts:
                    key = f"artifact_{artifact['id']}"
                    if st.button(f"Prepare download · {artifact['name']}", key=key):
                        with st.spinner("Artifact download ပြင်ဆင်နေပါသည်..."):
                            st.session_state[f"bytes_{key}"] = client.download_artifact(artifact["id"])
                    if st.session_state.get(f"bytes_{key}"):
                        st.download_button(
                            "Download ZIP", st.session_state[f"bytes_{key}"],
                            file_name=f"{artifact['name']}.zip", key=f"download_{key}",
                        )
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
    st.markdown("## ✦ AETHER\n**GITHUB EDITION**")
    page = st.radio("Workspace", ["Dashboard", "Create Studio", "Settings"], label_visibility="collapsed")
    st.divider()
    st.caption("Streamlit UI · GitHub Actions Worker")
    if st.button("Lock studio"):
        st.session_state.authenticated = False
        st.rerun()

if page == "Dashboard":
    dashboard_page()
elif page == "Settings":
    settings_page()
else:
    create_page()
