#!/bin/bash
# ========================================================
# IVIA Humanoid Companion - Raspberry Pi 4 (2GB) Setup Script
# Automates: Swap expansion, Docker install, and Auto-boot setup
# ========================================================

set -e

echo "========================================================"
echo "    IVIA AI BRAIN - RASPBERRY PI 4 SETUP"
echo "========================================================"

# 1. Setup 2GB Swap Memory (Crucial for 2GB Ubuntu Desktop)
CURRENT_SWAP=$(free -m | awk '/Swap:/ {print $2}')
if [ "$CURRENT_SWAP" -lt 1500 ]; then
    echo "[1/5] Configuring 2GB Swap Memory to prevent OOM on 2GB RAM..."
    sudo swapoff -a || true
    sudo fallocate -l 2G /swapfile || sudo dd if=/dev/zero of=/swapfile bs=1M count=2048
    sudo chmod 600 /swapfile
    sudo mkswap /swapfile
    sudo swapon /swapfile
    if ! grep -q "/swapfile" /etc/fstab; then
        echo '/swapfile none swap sw 0 0' | sudo tee -a /etc/fstab
    fi
    echo "      Swap memory successfully set to 2GB!"
else
    echo "[1/5] Swap memory already configured (${CURRENT_SWAP}MB). Skipping."
fi

# 2. Install Docker if not already installed
if ! command -v docker &> /dev/null; then
    echo "[2/5] Installing Docker..."
    curl -fsSL https://get.docker.com | sh
    sudo usermod -aG docker $USER
    echo "      Docker installed successfully."
else
    echo "[2/5] Docker is already installed."
fi

# 3. Ensure Docker starts automatically on boot
echo "[3/5] Enabling Docker service on system boot..."
sudo systemctl enable docker
sudo systemctl start docker

# 4. Check .env configuration
echo "[4/5] Checking environment configuration..."
if [ ! -f .env ]; then
    if [ -f .env.example ]; then
        cp .env.example .env
        echo "      Created .env from .env.example."
        echo "      >>> IMPORTANT: Edit .env and add your GROQ_API_KEY! <<<"
    fi
else
    echo "      Found existing .env file."
fi

# 5. Build and launch the container
echo "[5/5] Building and launching IVIA Brain container..."
sudo docker compose up -d --build

# Get local IP address
PI_IP=$(hostname -I | awk '{print $1}')

echo ""
echo "========================================================"
echo "    IVIA AI BRAIN IS NOW ONLINE & AUTO-STARTING ON BOOT!"
echo "========================================================"
echo " Raspberry Pi Local IP: $PI_IP"
echo " Web Dashboard:        http://$PI_IP:8000"
echo ""
echo " >>> NEXT STEP FOR ESP32-S3 FIRMWARE: <<<"
echo " In Arduino IDE on your PC, open 'esp32_s3_audio_node/config.h':"
echo "   #define SERVER_HOST \"$PI_IP\""
echo "   #define SERVER_PORT 8000"
echo "   #define USE_SSL     false"
echo " Then flash the ESP32-S3 via USB!"
echo "========================================================"
