FROM python:3.12-slim

# FFmpeg နှင့် မြန်မာစာ font shaping အတွက် system packages
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg fonts-noto-core fonts-noto-extra curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .

ENV PYTHONUNBUFFERED=1 \
    AETHER_DATA_DIR=/app/data \
    FFMPEG_BINARY=ffmpeg \
    FFPROBE_BINARY=ffprobe

EXPOSE 8501
CMD ["streamlit", "run", "app.py", "--server.address=0.0.0.0"]
