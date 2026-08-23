# AETHER FILMWORKS · GitHub + Streamlit Edition · Build 55.1 Pro

Streamlit Community Cloud ကို clean UI အဖြစ်အသုံးပြုပြီး GitHub Actions ကို
detached background video worker အဖြစ်အသုံးပြုထားသော AETHER Studio ဖြစ်သည်။
ဖုန်း screen ပိတ်ခြင်း၊ browser ပိတ်ခြင်း သို့မဟုတ် Streamlit session ပြတ်ခြင်းက
စတင်ပြီးသား GitHub Action ကို မရပ်စေပါ။

## ပါဝင်သော Studio modes

- Movie Dubbing / Burmese Recap
- Global Translation
- Faceless Channel
- Epic Series
- Veo Video
- Lyria Music

## Build 55 Pro တွင်အသစ်ပါဝင်သောအရာများ

- Completed job card ထဲတွင် full-length lightweight MP4 preview ကို တိုက်ရိုက်ကြည့်နိုင်ခြင်း
- Preview MP4 နှင့် output ZIP ကို သီးခြား download လုပ်နိုင်ခြင်း
- Noto Sans/Serif Myanmar font၊ font size၊ text/outline/background color ရွေးနိုင်သော Subtitle Designer
- Clean White, Gold Cinematic, Shorts Bold နှင့် Readable Box subtitle presets
- Top/Center/Bottom position၊ outline၊ shadow နှင့် mobile safe margin settings
- SRT download အပြင် styled ASS subtitle file ထုတ်ပေးခြင်း
- H.264/AAC/pixel format/duration စစ်ထားသော `render_report.json`
- Failed GitHub job ကို မူလ settings အတိုင်း Dashboard မှ retry လုပ်နိုင်ခြင်း
- Source media အသုံးပြုခွင့် confirmation နှင့် mobile-first layout
- Xiaohongshu/TikTok တို့တွင် resolution metadata မပြည့်စုံသည့် video များအတွက် yt-dlp format fallback

Preview သည် final video ကို 540px wide H.264 proxy အဖြစ်သာ ထပ် encode လုပ်သောကြောင့်
GPU မလိုဘဲ GitHub-hosted free runner တွင်သင့်တော်သည်။ Lip-sync၊ voice cloning နှင့်
heavy AI upscaling မပါဝင်သေးပါ။

## Architecture

```text
Phone / Browser
    ↓
Streamlit Community Cloud (app.py)
    ↓ workflow_dispatch
GitHub Actions (.github/workflows/aether-worker.yml)
    ↓
Gemini / Edge-TTS / FFmpeg
    ↓
GitHub Actions Artifact ZIP
```

Phone မှတင်သည့် MP4 ကို public repository history ထဲ commit မလုပ်ပါ။ Random job
ID ပါသည့် GitHub draft release asset အဖြစ် ယာယီတင်ပြီး worker ပြီးသည်နှင့်
ဖျက်သည်။ Worker မစနိုင်သည့် orphan upload များကို cleanup workflow က 12 နာရီ
ကျော်လျှင်ဖျက်သည်။ Streamlit Cloud memory အတွက် phone upload တစ်ဖိုင်ကို
အများဆုံး 500 MB သတ်မှတ်ထားသည်။

> Public repository ဖြစ်သည့်အတွက် လျှို့ဝှက်/private media အတွက် dedicated
> private storage မဟုတ်ပါ။ Draft staging နှင့် random ID က accidental exposure
> ကိုလျှော့ချပေးသော်လည်း အလွန်အရေးကြီးသော private video မတင်သင့်ပါ။

## 1. GitHub repository ထဲတင်ရန်

ZIP ထဲမှ ဖိုင်နှင့် folder အားလုံးကို repository root ထဲထည့်ပါ။ အထူးသဖြင့်—

```text
app.py
requirements.txt
packages.txt
runtime.txt
aether/
scripts/
.github/workflows/
.streamlit/config.toml
```

## 2. GitHub Actions secrets

GitHub repository → **Settings → Secrets and variables → Actions** တွင်—

```text
GEMINI_API_KEYS = key1,key2
GROQ_API_KEYS   = optional-groq-key
ELEVENLABS_API_KEY = optional-elevenlabs-key
TTSMAKER_API_KEY   = optional-ttsmaker-pro-key
```

Edge-TTS နှင့် Google Synergy သာသုံးမည်ဆိုလျှင် နောက်ဆုံး optional key နှစ်ခု
မလိုပါ။ Google Synergy သည် `GEMINI_API_KEYS` ကိုအသုံးပြုသည်။ TTSMaker API သည်
Free website plan မဟုတ်ဘဲ API ပါသော Pro/Studio plan လိုအပ်သည်။

ထည့်ပါ။ `AETHER_MODEL_PROFILE` ကို Actions Variable အဖြစ် `balanced`, `quality`
သို့မဟုတ် `economy` သတ်မှတ်နိုင်သည်။ Default သည် `balanced` ဖြစ်သည်။

Repository → **Settings → Actions → General → Workflow permissions** တွင်
**Read and write permissions** ရွေးပါ။ Temporary release cleanup အတွက်လိုအပ်သည်။

## 3. Fine-grained GitHub token

Streamlit က workflow trigger၊ draft release upload နဲ့ artifact download လုပ်နိုင်ရန်
fine-grained personal access token တစ်ခုဖန်တီးပါ။ ဒီ repository တစ်ခုတည်းကိုသာ
ရွေးပြီး repository permissions ကို—

```text
Actions:  Read and write
Contents: Read and write
Metadata: Read-only
```

ပေးပါ။ Token ကို public repository သို့ code ထဲ မထည့်ပါနှင့်။

## 4. Streamlit Community Cloud secrets

Streamlit app → **Manage app → Settings → Secrets** တွင်—

```toml
APP_PASSWORD = "your-strong-studio-password"
GITHUB_TOKEN = "github_pat_xxxxxxxxx"
GITHUB_REPOSITORY = "username/repository"
GITHUB_WORKFLOW = "aether-worker.yml"
GITHUB_BRANCH = "main"
AETHER_MODEL_PROFILE = "balanced"
```

ထည့်ပါ။ Public Streamlit URL ကို တခြားသူများက GitHub Actions minutes/API quota
မသုံးနိုင်အောင် `APP_PASSWORD` မဖြုတ်ပါနှင့်။

## 5. Streamlit deployment

Streamlit Community Cloud မှာ—

```text
Repository: username/repository
Branch: main
Main file path: app.py
```

ရွေးပြီး Deploy/Reboot လုပ်ပါ။ `packages.txt` က FFmpeg နှင့် Myanmar fonts ကို
တပ်ဆင်ပေးမည်။

## အသုံးပြုပုံ

1. Streamlit app ကိုဖွင့်ပြီး Studio password ဖြင့်ဝင်ပါ။
2. **Create Studio** မှ mode ရွေးပါ။
3. Phone MP4 upload သို့မဟုတ် public URL ထည့်ပါ။
4. **Start background job** နှိပ်ပါ။
5. Submit ပြီးကြောင်းပြလျှင် browser/phone ကိုပိတ်နိုင်သည်။
6. ပြန်ဝင်ပြီး Dashboard မှ status ကြည့်ပါ။
7. Completed ဖြစ်လျှင် **Load video preview** ဖြင့် browser ထဲတွင်စစ်ပါ။
8. Preview MP4 သို့မဟုတ် artifact ZIP ကို download လုပ်ပါ။

## Model router

Balanced profile သည်—

```text
Text/Translation: gemini-3.7-flash
Reasoning:        gemini-3.1-pro-preview
Image:            gemini-3.1-flash-image
TTS:              gemini-3.1-flash-tts-preview
Video:            veo-3.1-fast-generate-preview
Music:            lyria-3-pro-preview
```

ကိုအသုံးပြုသည်။ API timeout၊ media processing deadline၊ key rotation၊ 429/503
retry နှင့် free Pollinations image fallback ပါဝင်သည်။

## ကန့်သတ်ချက်များ

- GitHub-hosted runner minutes၊ artifact retention နှင့် workflow limits အတွင်းသာ run မည်။
- Short-form video workflow အတွက်သင့်တော်ပြီး full-length movie rendering များသည် အချိန်/နယ်ပယ်ပိုလိုနိုင်သည်။
- Artifact retention ကို workflow ထဲတွင် 14 ရက်ထားသည်။ မပျောက်ခင် download လုပ်ပါ။
- Veo/Lyria preview methods သည် account၊ region နှင့် installed SDK version အလိုက်ကွာနိုင်သည်။
