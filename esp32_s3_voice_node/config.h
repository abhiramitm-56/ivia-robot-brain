#ifndef CONFIG_H
#define CONFIG_H

// ==========================================
// Wi-Fi Configuration
// IMPORTANT: Both your PC and ESP32 MUST be connected to the SAME Wi-Fi!
// ==========================================
// Option 1: Mobile Hotspot (Connect PC to this hotspot too; run `ipconfig` on PC to get SERVER_HOST)
#define WIFI_SSID     "Abhirami"
#define WIFI_PASSWORD "123454321"
#define SERVER_HOST   "10.35.199.251" // Change to your PC's IP on this hotspot

// Option 2: Router Wi-Fi (Active PC Wi-Fi: NextGenPro_4G -> IP: 192.168.29.54)
// #define WIFI_SSID     "NextGenPro_4G"
// #define WIFI_PASSWORD "YOUR_WIFI_PASSWORD"
// #define SERVER_HOST   "192.168.29.54"

#define SERVER_PORT   8000            // 8000 for local PC, 443 for Cloud
#define WS_PATH       "/ws/esp32"
#define USE_SSL       false           // false = local PC, true = Cloud (HTTPS/WSS)

// ==========================================
// Audio Settings
// Standard 16kHz 16-bit Mono for Voice AI
// ==========================================
#define SAMPLE_RATE   16000
#define I2S_READ_LEN  1024
#define I2S_WRITE_LEN 1024

// ==========================================
// ESP32-S3 DevKit N16R8 Pin Configuration
// Tested and confirmed pins matching 44-pin DevKit header
// ==========================================

// --- INMP441 Digital Microphone (I2S_NUM_0 - RX) ---
// VDD -> 3.3V (Left Header, Pin 1 or 2), GND -> GND, L/R -> GND (Left channel)
#define I2S_MIC_SCK   41      // Right Header, Pin 7 (SCK / Bit Clock)
#define I2S_MIC_WS    42      // Right Header, Pin 6 (WS / Word Select)
#define I2S_MIC_SD    2       // Right Header, Pin 5 (SD / Serial Data In)

// --- MAX98357A I2S Amplifier (I2S_NUM_1 - TX) ---
// VIN -> 5V (Left Header, Pin 21), GND -> GND (Left Header, Pin 22)
// SD & GAIN -> Leave unconnected
#define I2S_SPK_BCLK  1       // Right Header, Pin 4 (BCLK / Bit Clock)
#define I2S_SPK_LRC   14      // Left Header, Pin 20 (LRC / Left-Right Clock)
#define I2S_SPK_DIN   21      // Right Header, Pin 18 (DIN / Serial Data Out)

#endif // CONFIG_H
