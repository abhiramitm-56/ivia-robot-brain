# ========================================================
# IVIA AI Humanoid Brain - Cloud Server Dockerfile (Render.com)
# ========================================================

FROM python:3.11-slim

# Install system audio, vision, and networking libraries
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    libsndfile1 \
    libgl1 \
    libglib2.0-0 \
    curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python requirements
COPY requirements_cloud.txt requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code and vision models
COPY server/ /app/server/
COPY web/ /app/web/
COPY yolov8n.pt /app/yolov8n.pt
COPY gesture_recognizer.task /app/gesture_recognizer.task

ENV PORT=8000
EXPOSE 8000

CMD ["sh", "-c", "uvicorn server.app:app --host 0.0.0.0 --port ${PORT:-8000}"]
