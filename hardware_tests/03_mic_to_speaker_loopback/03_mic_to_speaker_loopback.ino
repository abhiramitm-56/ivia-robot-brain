/**
 * TEST 3: Hardware Audio Loopback (Mic -> Speaker Pass-through)
 * Board: ESP32-S3 (N16R8)
 * 
 * Tests both audio peripherals working together in real time:
 *   - INMP441 on I2S_NUM_0 (SCK: 41, WS: 42, SD: 2)
 *   - MAX98357A on I2S_NUM_1 (BCLK: 1, LRC: 14, DIN: 21)
 * 
 * Result:
 *   Acts as an instant digital megaphone!
 *   Speak into the microphone and you will hear your own voice live through the speaker.
 *   (Keep speaker 20-30cm away from the mic or lower volume to prevent acoustic feedback howl).
 */

#include <Arduino.h>
#include "driver/i2s.h"

// Microphone Pins (I2S_NUM_0 - RX)
#define I2S_MIC_SCK 41
#define I2S_MIC_WS  42
#define I2S_MIC_SD  2

// Speaker Pins (I2S_NUM_1 - TX)
#define I2S_SPK_BCLK 1
#define I2S_SPK_LRC  14
#define I2S_SPK_DIN  21

#define SAMPLE_RATE 16000

void initI2SPeripherals() {
    // 1. Configure INMP441 Microphone (I2S_NUM_0)
    i2s_config_t mic_config = {
        .mode = (i2s_mode_t)(I2S_MODE_MASTER | I2S_MODE_RX),
        .sample_rate = SAMPLE_RATE,
        .bits_per_sample = I2S_BITS_PER_SAMPLE_32BIT,
        .channel_format = I2S_CHANNEL_FMT_ONLY_LEFT,
        .communication_format = i2s_comm_format_t(I2S_COMM_FORMAT_STAND_I2S),
        .intr_alloc_flags = ESP_INTR_FLAG_LEVEL1,
        .dma_buf_count = 4,
        .dma_buf_len = 256,
        .use_apll = false,
        .tx_desc_auto_clear = false
    };

    i2s_pin_config_t mic_pins = {
        .bck_io_num = I2S_MIC_SCK,
        .ws_io_num = I2S_MIC_WS,
        .data_out_num = I2S_PIN_NO_CHANGE,
        .data_in_num = I2S_MIC_SD
    };

    i2s_driver_install(I2S_NUM_0, &mic_config, 0, NULL);
    i2s_set_pin(I2S_NUM_0, &mic_pins);

    // 2. Configure MAX98357A Speaker (I2S_NUM_1)
    i2s_config_t spk_config = {
        .mode = (i2s_mode_t)(I2S_MODE_MASTER | I2S_MODE_TX),
        .sample_rate = SAMPLE_RATE,
        .bits_per_sample = I2S_BITS_PER_SAMPLE_16BIT,
        .channel_format = I2S_CHANNEL_FMT_RIGHT_LEFT,
        .communication_format = i2s_comm_format_t(I2S_COMM_FORMAT_STAND_I2S),
        .intr_alloc_flags = ESP_INTR_FLAG_LEVEL1,
        .dma_buf_count = 4,
        .dma_buf_len = 256,
        .use_apll = false,
        .tx_desc_auto_clear = true
    };

    i2s_pin_config_t spk_pins = {
        .bck_io_num = I2S_SPK_BCLK,
        .ws_io_num = I2S_SPK_LRC,
        .data_out_num = I2S_SPK_DIN,
        .data_in_num = I2S_PIN_NO_CHANGE
    };

    i2s_driver_install(I2S_NUM_1, &spk_config, 0, NULL);
    i2s_set_pin(I2S_NUM_1, &spk_pins);

    Serial.println("[Loopback] Dual I2S initialized successfully!");
}

void setup() {
    Serial.begin(115200);
    delay(1000);
    Serial.println("\n=============================================");
    Serial.println("  TEST 3: HARDWARE AUDIO LOOPBACK (MEGAPHONE)");
    Serial.println("=============================================");
    Serial.println("Speak into the mic. Your voice will play from the speaker in real-time.");
    initI2SPeripherals();
}

void loop() {
    int32_t rx_buffer[128];
    int16_t tx_buffer[128 * 2]; // Stereo (L + R)
    size_t bytes_read = 0;
    size_t bytes_written = 0;

    // Read audio chunk from INMP441
    esp_err_t result = i2s_read(I2S_NUM_0, rx_buffer, sizeof(rx_buffer), &bytes_read, portMAX_DELAY);
    if (result == ESP_OK && bytes_read > 0) {
        size_t samples = bytes_read / sizeof(int32_t);

        // Convert 32-bit mic input to 16-bit stereo speaker output
        for (size_t i = 0; i < samples; i++) {
            int16_t s = (int16_t)(rx_buffer[i] >> 14);
            tx_buffer[i * 2] = s;     // Left
            tx_buffer[i * 2 + 1] = s; // Right
        }

        // Write directly to MAX98357A speaker
        i2s_write(I2S_NUM_1, tx_buffer, samples * 4, &bytes_written, portMAX_DELAY);
    }
}
