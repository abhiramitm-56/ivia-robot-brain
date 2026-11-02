#ifndef CONFIG_H
#define CONFIG_H

// ==========================================
// 1. Wi-Fi Configuration
// ==========================================
// Connect PC and ESP32 to the same Wi-Fi network / Hotspot:
#define WIFI_SSID     "Abhirami"        // Your Wi-Fi / Hotspot SSID
#define WIFI_PASSWORD "123454321"       // Your Wi-Fi / Hotspot Password

// PC's local IP (if testing locally) OR your Cloud Domain (e.g. "ivia-brain.onrender.com" or "user-ivia.hf.space")
#define SERVER_HOST   "10.35.199.251"   
#define SERVER_PORT   8000              // 8000 for local PC, 443 for Cloud (Render / Hugging Face / Railway)
#define WS_PATH       "/ws/esp32"

// Set to true when connecting to a Cloud server over HTTPS / WSS:
#define USE_SSL       false             // false = local PC (HTTP/WS), true = Cloud (HTTPS/WSS)

// ==========================================
// 2. Audio Configuration (16kHz 16-bit Mono)
// ==========================================
#define SAMPLE_RATE   16000

// ==========================================
// 3. Audio Pinout for ESP32-S3-DEV-KIT-N16R8
// Tested and verified against standard 44-pin DevKit header
// ==========================================

// --- INMP441 Microphone (I2S_NUM_0 - RX) ---
// VDD -> 3V3 (Left Header, Pin 1 or 2)
// GND -> GND (Right Header, Pin 1)
// L/R -> GND (Left channel mono)
#define I2S_MIC_SCK   41   // Right Header, Pin 7 (SCK / Bit Clock)
#define I2S_MIC_WS    42   // Right Header, Pin 6 (WS / Word Select)
#define I2S_MIC_SD    2    // Right Header, Pin 5 (SD / Serial Data In)

// --- MAX98357A Amplifier (I2S_NUM_1 - TX) ---
// VIN -> 5V0 (Left Header, Pin 21 - Full 3.2W power)
// GND -> GND (Left Header, Pin 22)
// GAIN -> Leave Open (defaults to +9dB)
// SD   -> Leave Open
#define I2S_SPK_BCLK  1    // Right Header, Pin 4 (BCLK / Bit Clock)
#define I2S_SPK_LRC   14   // Left Header, Pin 20 (LRC / Left-Right Clock)
#define I2S_SPK_DIN   21   // Right Header, Pin 18 (DIN / Serial Data Out)

#endif // CONFIG_H

