#ifndef CONFIG_H
#define CONFIG_H

// ==========================================
// 1. Wi-Fi Configuration (Supports Multiple Networks)
// The ESP32 will automatically connect to whichever is available!
// ==========================================
#define WIFI_SSID_1     "Abhirami"        // Primary: Mobile Hotspot SSID
#define WIFI_PASSWORD_1 "123454321"       // Primary: Mobile Hotspot Password

#define WIFI_SSID_2     ""                // Secondary: Home/Office Wi-Fi (optional)
#define WIFI_PASSWORD_2 ""                // Secondary: Home/Office Password (optional)

// ==========================================
// 2. Server Connection (Render Cloud - 24/7 Standalone)
// ==========================================
#define SERVER_HOST   "ivia-robot-brain.onrender.com"   
#define SERVER_PORT   443              // Standard secure SSL port
#define WS_PATH       "/ws/esp32"
#define USE_SSL       true             // true for Render Cloud (WSS)

// ==========================================
// 3. Audio Configuration (16kHz 16-bit Mono)
// ==========================================
#define SAMPLE_RATE   16000

// ==========================================
// 4. Audio Pinout for ESP32-S3-DEV-KIT-N16R8
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
