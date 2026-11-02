# IVIA Standalone Audio Node (ESP32-S3 DevKit N16R8)

Dedicated voice node for the IVIA Humanoid Companion robot. Runs on a standard **ESP32-S3 DevKit (N16R8)** with **INMP441 Microphone** and **MAX98357A I2S Amplifier**.

---

## Hardware Pin Connections

### 1. INMP441 Digital Microphone (Audio Input)
| INMP441 Pin | ESP32-S3 Pin | Physical Location on DevKit | Function |
| :--- | :--- | :--- | :--- |
| **VDD** | **3V3** | **Left Header, Pin 1 or 2** (Top-Left) | Power (**Do NOT connect to 5V!**) |
| **GND** | **GND** | **Right Header, Pin 1** (Top-Right) | Ground |
| **L/R** | **GND** | Connect to **GND** | Left Channel (Mono) |
| **SCK** | **GPIO 41** | **Right Header, Pin 7** | Bit Clock (BCLK) |
| **WS** | **GPIO 42** | **Right Header, Pin 6** | Word Select (LRC) |
| **SD** | **GPIO 2** | **Right Header, Pin 5** | Serial Data (SD) |

### 2. MAX98357A I2S Amplifier (Audio Output)
| MAX98357A Pin | ESP32-S3 Pin | Physical Location on DevKit | Function |
| :--- | :--- | :--- | :--- |
| **VIN** | **5V0** | **Left Header, Pin 21** (Bottom-Left) | 5V Power for full 3.2W output |
| **GND** | **GND** | **Left Header, Pin 22** (Bottom-Left) | Ground |
| **BCLK** | **GPIO 1** | **Right Header, Pin 4** | Bit Clock |
| **LRC** | **GPIO 14** | **Left Header, Pin 20** | Left/Right Clock (Next to 5V0) |
| **DIN** | **GPIO 21** | **Right Header, Pin 18** | Serial Audio Data In |
| **GAIN** | *Leave Open* | *Unconnected* | Defaults to +9dB |
| **SD** | *Leave Open* | *Unconnected* | Defaults to stereo downmix |
| **Speaker +/-**| **Speaker** | Screw terminals | Connect 4Ω or 8Ω speaker |

> ⚠️ **CRITICAL NOTE:** On ESP32-S3 N16R8, **GPIO 35, 36, and 37** are tied to Octal PSRAM. Never connect anything to them.

---

## Arduino IDE Configuration
- **Board:** `ESP32S3 Dev Module`
- **PSRAM:** `OPI PSRAM`
- **Flash Size:** `16MB (128Mb)`
- **USB CDC On Boot:** `Enabled`
- **Upload Speed:** `921600`

---

## How to Run

1. Open `esp32_s3_audio_node.ino` in Arduino IDE.
2. In `config.h`, ensure `WIFI_SSID`, `WIFI_PASSWORD`, and `SERVER_HOST` (your PC IP) are correct.
3. Upload to the ESP32-S3 DevKit.
4. On your PC, double-click `run_chatbot.bat`.
5. Speak into the INMP441 microphone — IVIA will answer through the speaker!

