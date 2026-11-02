/**
 * TEST 2: INMP441 I2S Digital Microphone Test
 * Board: ESP32-S3 (N16R8)
 * 
 * Wiring:
 *   INMP441 VDD -> 3.3V
 *   INMP441 GND -> GND
 *   INMP441 L/R -> GND (Left channel)
 *   INMP441 SCK -> GPIO 41
 *   INMP441 WS  -> GPIO 42
 *   INMP441 SD  -> GPIO 2
 * 
 * Result:
 *   Prints a live real-time ASCII Volume Meter (VU meter) in the Serial Monitor (115200 baud).
 *   When you speak, snap, or tap near the mic, the volume bars expand!
 *   No Wi-Fi or server needed.
 */

#include <Arduino.h>
#include "driver/i2s.h"
#include <math.h>

#define I2S_MIC_SCK 41
#define I2S_MIC_WS  42
#define I2S_MIC_SD  2
#define SAMPLE_RATE 16000

void initMicrophone() {
    i2s_config_t i2s_config = {
        .mode = (i2s_mode_t)(I2S_MODE_MASTER | I2S_MODE_RX),
        .sample_rate = SAMPLE_RATE,
        .bits_per_sample = I2S_BITS_PER_SAMPLE_32BIT, // INMP441 outputs 24-bit in 32-bit slot
        .channel_format = I2S_CHANNEL_FMT_ONLY_LEFT,
        .communication_format = i2s_comm_format_t(I2S_COMM_FORMAT_STAND_I2S),
        .intr_alloc_flags = ESP_INTR_FLAG_LEVEL1,
        .dma_buf_count = 8,
        .dma_buf_len = 256,
        .use_apll = false,
        .tx_desc_auto_clear = false
    };

    i2s_pin_config_t pin_config = {
        .bck_io_num = I2S_MIC_SCK,
        .ws_io_num = I2S_MIC_WS,
        .data_out_num = I2S_PIN_NO_CHANGE,
        .data_in_num = I2S_MIC_SD
    };

    i2s_driver_install(I2S_NUM_0, &i2s_config, 0, NULL);
    i2s_set_pin(I2S_NUM_0, &pin_config);
    Serial.println("[Mic Test] INMP441 I2S initialized on SCK:41, WS:42, SD:2");
}

void setup() {
    Serial.begin(115200);
    delay(1000);
    Serial.println("\n========================================");
    Serial.println("   TEST 2: INMP441 MICROPHONE TEST       ");
    Serial.println("========================================");
    Serial.println("Speak or tap the mic. The ASCII bar will jump!");
    initMicrophone();
}

void loop() {
    int32_t raw_buffer[128];
    size_t bytes_read = 0;

    esp_err_t result = i2s_read(I2S_NUM_0, raw_buffer, sizeof(raw_buffer), &bytes_read, pdMS_TO_TICKS(50));
    if (result == ESP_OK && bytes_read > 0) {
        size_t samples = bytes_read / sizeof(int32_t);
        int64_t sum_squares = 0;
        int16_t peak = 0;

        for (size_t i = 0; i < samples; i++) {
            // Shift 32-bit sample to 16-bit
            int16_t sample16 = (int16_t)(raw_buffer[i] >> 14);
            int16_t abs_s = abs(sample16);
            if (abs_s > peak) peak = abs_s;
            sum_squares += (int32_t)sample16 * sample16;
        }

        int rms = sqrt(sum_squares / samples);

        // Map RMS (0 to 3000) to 30 ASCII bar characters
        int barLength = map(constrain(rms, 0, 2500), 0, 2500, 0, 30);
        
        Serial.print("[VU Meter] [");
        for (int b = 0; b < 30; b++) {
            if (b < barLength) Serial.print("|");
            else Serial.print(" ");
        }
        Serial.printf("]  RMS: %4d  Peak: %5d", rms, peak);
        if (rms > 600) {
            Serial.print("  <-- SOUND DETECTED!");
        }
        Serial.println();
    }
    delay(40);
}
