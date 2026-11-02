#ifndef CONFIG_H
#define CONFIG_H

// ==========================================
// Wi-Fi Configuration
// Replace with your Wi-Fi credentials
// ==========================================
#define WIFI_SSID     "YOUR_WIFI_SSID"
#define WIFI_PASSWORD "YOUR_WIFI_PASSWORD"

// ==========================================
// Backend Server Configuration
// Replace with the local IP of your PC/Server
// Example: 192.168.1.100 (Do NOT use localhost or 127.0.0.1)
// ==========================================
#define SERVER_HOST   "192.168.1.100"
#define SERVER_PORT   8000
#define WS_PATH       "/ws/esp32"

// ==========================================
// Audio Settings
// Standard 16kHz 16-bit Mono for Voice AI
// ==========================================
#define SAMPLE_RATE   16000
#define I2S_READ_LEN  1024    // Bytes read per cycle
#define I2S_WRITE_LEN 1024

// ==========================================
// Hardware Pin Configuration (ESP32 Dev Module)
// ==========================================

// --- INMP441 Digital Microphone (I2S_NUM_0 - RX) ---
// Connect L/R pin of INMP441 to GND
#define I2S_MIC_WS    25      // Word Select (LRC)
#define I2S_MIC_SCK   33      // Serial Clock (BCLK)
#define I2S_MIC_SD    32      // Serial Data In (DIN / SD)

// --- MAX98357A I2S Amplifier (I2S_NUM_1 - TX) ---
// Connect GAIN to GND (default gain), VIN to 5V (or 3.3V)
#define I2S_SPK_BCLK  26      // Bit Clock
#define I2S_SPK_LRC   27      // Left/Right Clock (WS)
#define I2S_SPK_DIN   22      // Data Out (DIN)

#endif // CONFIG_H
