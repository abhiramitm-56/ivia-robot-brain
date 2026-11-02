# Hardware Test 5: Standalone OV3660 Vision Dashboard

Standalone object and gesture recognition test for the **ESP32-S3 N16R8** with an **OV3660 camera module**.

---

## What It Does
* **High-FPS Video Stream:** Streams live 640x480 VGA video from the ESP32-S3 OV3660 using Octal PSRAM.
* **Real-Time Object Detection:** Identifies 80 common objects (person, phone, bottle, cup, laptop, etc.) with bounding boxes and confidence scores using YOLOv8.
* **Hand Gesture Recognition:** Tracks 21 hand landmarks and recognizes gestures using Google MediaPipe:
  * Open Hand / Wave / Stop
  * Fist
  * Thumbs Up
  * Peace / Victory (V)
  * Pointing
  * OK Sign
  * Rock On / Horns
* **Live "What it says" Dashboard Banner:** Dynamically synthesizes detections into real-time plain English narration (e.g. `What it says: "I see 1 person, 1 cell phone | Gesture: Thumbs Up"`).

---

## Quick Start Instructions

### 1. Flash the ESP32-S3 Firmware
1. Open Arduino IDE.
2. Open `05_ov3660_vision_dashboard.ino` (or use your already flashed `04_ov3660_camera_test.ino`—both work!).
3. If using `05_ov3660_vision_dashboard.ino`, check your Wi-Fi name and password:
   ```cpp
   const char* ssid = "Abhirami";
   const char* password = "123454321";
   ```
4. In Arduino IDE **Tools** menu:
   * **Board:** `ESP32S3 Dev Module`
   * **PSRAM:** `OPI PSRAM` *(Required for 8MB Octal PSRAM on N16R8)*
   * **Flash Size:** `16MB (128Mb)`
   * **USB CDC On Boot:** `Enabled`
5. Click **Upload**.
6. Open **Serial Monitor** at `115200` baud and note the IP address (e.g. `192.168.1.100`).

---

### 2. Run the Vision Dashboard (PC)

#### Option A: 1-Click Batch Runner (Windows)
Double-click `run_dashboard.bat`, enter your ESP32's IP address when prompted, and press Enter.

#### Option B: From Command Line
1. Open PowerShell or Command Prompt:
   ```powershell
   cd c:\Users\ABHIRAMI\Desktop\VOICE_OF_IVIA\hardware_tests\05_ov3660_vision_dashboard
   ```
2. Install requirements:
   ```powershell
   pip install -r requirements.txt
   ```
3. Run the dashboard with your ESP32 IP:
   ```powershell
   python vision_dashboard.py --ip <YOUR_ESP32_IP>
   ```

---

## Keyboard Shortcuts
| Key | Action |
| --- | --- |
| `q` | Quit dashboard |
| `s` | Save high-res snapshot (`capture_<timestamp>.jpg`) |
| `f` | Flip video horizontally |

