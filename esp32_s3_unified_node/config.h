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

#define SERVER_PORT   8000
#define WS_PATH       "/ws/esp32"

// ==========================================
// Audio Settings (16kHz 16-bit Mono)
// ==========================================
#define SAMPLE_RATE   16000
#define I2S_READ_LEN  1024
#define I2S_WRITE_LEN 1024

// ==========================================
// Audio Pins (Tested on ESP32-S3 N16R8)
// ==========================================
// --- INMP441 Digital Microphone (I2S_NUM_0 - RX) ---
// VDD -> 3.3V, GND -> GND, L/R -> GND
#define I2S_MIC_SCK   41      // Bit Clock (BCLK)
#define I2S_MIC_WS    42      // Word Select (LRC)
#define I2S_MIC_SD    2       // Serial Data In (SD)

// --- MAX98357A I2S Amplifier (I2S_NUM_1 - TX) ---
// VIN -> 5V or 3.3V, GND -> GND, SD & GAIN -> Unconnected
#define I2S_SPK_BCLK  1       // Bit Clock
#define I2S_SPK_LRC   14      // Word Select (LRC)
#define I2S_SPK_DIN   21      // Serial Data Out (DIN)

// ==========================================
// OV3660 Camera Pins (Zero Conflict with Audio!)
// ==========================================
#define PWDN_GPIO_NUM  -1
#define RESET_GPIO_NUM -1
#define XCLK_GPIO_NUM  15
#define SIOD_GPIO_NUM  4
#define SIOC_GPIO_NUM  5

#define Y9_GPIO_NUM    16
#define Y8_GPIO_NUM    17
#define Y7_GPIO_NUM    18
#define Y6_GPIO_NUM    12
#define Y5_GPIO_NUM    10
#define Y4_GPIO_NUM    8
#define Y3_GPIO_NUM    9
#define Y2_GPIO_NUM    11
#define VSYNC_GPIO_NUM 6
#define HREF_GPIO_NUM  7
#define PCLK_GPIO_NUM  13

#endif // CONFIG_H
