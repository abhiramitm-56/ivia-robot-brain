# IVIA — AI Humanoid Companion (Unified ESP32-S3 System)

**IVIA** is an interactive AI humanoid robot running on a single **ESP32-S3 N16R8 (with OV3660 camera)** module:
1. **Section 1: Voice Assistant & World Knowledge** (Powered by INMP441 Microphone + MAX98357A I2S Amplifier + Neural TTS).
2. **Section 2: Real-time Object Detection** (Powered by OV3660 Camera Sensor + 8MB PSRAM).
3. **Interactive Web Portal**: Cybernetic monitoring dashboard with live voice transcripts, frequency visualizer, and mode switcher.

---

## Hardware Pinout (ESP32-S3 N16R8 Tested & Verified)

### 1. INMP441 Digital Microphone (I2S Audio In $\to$ ESP32-S3)
| INMP441 Pin | ESP32-S3 Pin | Function / Description |
| :--- | :--- | :--- |
| **VDD** | **3.3V** | Power (Do NOT connect to 5V) |
| **GND** | **GND** | Ground |
| **L/R** | **GND** | Tie to GND to select Left Channel |
| **SCK** | **GPIO 41** | Serial Clock / Bit Clock (BCLK) |
| **WS** | **GPIO 42** | Word Select / Left-Right Clock (LRC) |
| **SD** | **GPIO 2** | Serial Data In (Data from Mic) |

---

### 2. MAX98357A I2S Class-D Amplifier (ESP32-S3 $\to$ Speaker Audio Out)
| MAX98357A Pin | ESP32-S3 Pin | Function / Description |
| :--- | :--- | :--- |
| **VIN** | **5V (or 3.3V)** | Power (5V provides louder, richer sound) |
| **GND** | **GND** | Ground |
| **BCLK** | **GPIO 1** | Bit Clock |
| **LRC** | **GPIO 14** | Word Select / Left-Right Clock |
| **DIN** | **GPIO 21** | Serial Data Out (Audio to Amp) |
| **SD & GAIN** | **Leave Unconnected** | Default channel and gain (+9dB) |
| **Speaker +/-** | **Speaker Terminals** | Connect your 4Ω or 8Ω speaker |

---

## One-By-One Component Testing Suite

Before flashing the full robot firmware, test each component individually using the sketches in `hardware_tests/`:

### Test 1: Speaker & Amplifier (`hardware_tests/01_speaker_sine_test/`)
* **Goal**: Verifies the MAX98357A amp and speaker without Wi-Fi or server.
* **How to run**: Open the sketch in Arduino IDE, select `ESP32S3 Dev Module`, and upload.
* **Expected result**: Plays a pleasant repeating chime melody (440Hz $\to$ 659Hz $\to$ 880Hz).

### Test 2: Microphone & Audio In (`hardware_tests/02_mic_serial_test/`)
* **Goal**: Verifies the INMP441 microphone and audio capture without Wi-Fi or server.
* **How to run**: Upload sketch and open the Serial Monitor (115200 baud).
* **Expected result**: Displays an interactive ASCII VU meter bar `[||||||||||||        ]`. When you speak, snap, or tap the mic, the bar expands and detects audio!

### Test 3: Hardware Loopback / Megaphone (`hardware_tests/03_mic_to_speaker_loopback/`)
* **Goal**: Proves both I2S controllers work simultaneously on the ESP32-S3 without DMA collisions.
* **How to run**: Upload sketch.
* **Expected result**: Speak into the INMP441 mic $\to$ your voice comes directly out of the speaker in real time!

### Test 4: OV3660 Camera Live Stream (`hardware_tests/04_ov3660_camera_test/`)
* **Goal**: Verifies the OV3660 camera sensor, ribbon cable, and 8MB PSRAM.
* **How to run**: In Arduino IDE, ensure **Tools $\to$ PSRAM: "OPI PSRAM"** is selected. Put your Wi-Fi details in the sketch and upload.
* **Expected result**: Connects to Wi-Fi and prints `http://<ESP32_IP>/`. Open that URL in your browser to view the live camera video stream!

---

## Pronunciation Corrections

The system includes pre-configured phonetic text preprocessing in `server/config.py` and `server/tts_engine.py`:
* **IVIA**: Phonetically spoken as `"Eye-vee-ah"` (or `"Ee-vee-ah"`) so the neural voice pronounces it as a warm name rather than spelling out the letters *"I-V-I-A"*.

You can tweak the exact phonetic spelling anytime in your `.env` file:
```env
IVIA_PHONETIC=Eye-vee-ah
```

---

## Running the Complete System

### 1. Start the Brain Server
```powershell
cd c:\Users\ABHIRAMI\Desktop\VOICE_OF_IVIA
.venv\Scripts\python -m uvicorn server.app:app --host 0.0.0.0 --port 8000
```
Open **`http://localhost:8000`** in your browser.

### 2. Upload the Unified ESP32-S3 Firmware
1. Open [`esp32_s3_voice_node/esp32_s3_voice_node.ino`](file:///c:/Users/ABHIRAMI/Desktop/VOICE_OF_IVIA/esp32_s3_voice_node/esp32_s3_voice_node.ino) in Arduino IDE.
2. In [`config.h`](file:///c:/Users/ABHIRAMI/Desktop/VOICE_OF_IVIA/esp32_s3_voice_node/config.h), set your Wi-Fi SSID, Password, and your PC's IP (`SERVER_HOST`).
3. Arduino IDE Tools settings:
   - **Board**: `"ESP32S3 Dev Module"`
   - **PSRAM**: `"OPI PSRAM"`
   - **Flash Size**: `"16MB"`
   - **USB CDC On Boot**: `"Enabled"`
4. Click **Upload**.
5. Once uploaded, the web portal will turn green: **ESP32 Voice Node Active**!

---

## Section 2: Real-time Object & Hand Gesture Detection

IVIA features a unified computer vision pipeline combining **YOLOv8** and **MediaPipe Hand Gesture Recognition**:

### 1. Detection Capabilities
* **👤 Persons**: Instant human presence detection with bounding box and confidence score.
* **📱 Small Objects**: Real-time identification of everyday objects such as:
  * Cell phones, cups, bottles, remotes, laptops, mice, keyboards
  * Books, scissors, glasses, clocks, backpacks, umbrellas, etc.
* **🖐️ Hand Gestures & 21-Landmark Skeleton**:
  * 🖐️ **Open Palm / Wave / Stop**
  * ✊ **Closed Fist**
  * 👍 **Thumbs Up**
  * 👎 **Thumbs Down**
  * ✌️ **Peace / Victory ('V' Sign)**
  * ☝️ **Pointing Up**
  * 👌 **OK Sign**
  * 🤏 **Pinch**
  * 🤘 **Rock On / Love**
  * Full 21-point neon skeleton overlay with Left / Right hand tracking.

### 2. How to Use & Test
1. Open **`http://localhost:8000`** in your browser.
2. Switch to **Section 2: Object Detection (ESP32-S3)** tab.
3. Choose your input source:
   * **WebCam (Laptop / USB)**: Click **"Start Camera Feed"** to test with your computer's webcam instantly!
   * **ESP32-S3 (OV3660)**: Enter your ESP32's IP address (from Serial Monitor after uploading `04_ov3660_camera_test`) and click **"Start Camera Feed"**.
4. Use filter toggles (**Persons**, **Small Things**, **Hand Gestures**) to customize what is highlighted.
5. **Ask IVIA through voice or chat**:
   * *"What do you see right now?"*
   * *"What am I holding in my hand?"*
   * *"What hand gesture am I showing you?"*
   * IVIA checks her real-time visual telemetry and answers naturally through the speaker!

