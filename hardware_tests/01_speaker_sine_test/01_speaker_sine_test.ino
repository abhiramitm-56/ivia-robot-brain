/**
 * TEST 1: MAX98357A I2S Amplifier & Speaker Test
 * Board: ESP32-S3 (N16R8)
 * 
 * Wiring:
 *   MAX98357A VIN  -> 5V (or 3.3V)
 *   MAX98357A GND  -> GND
 *   MAX98357A BCLK -> GPIO 1
 *   MAX98357A LRC  -> GPIO 14
 *   MAX98357A DIN  -> GPIO 21
 *   MAX98357A GAIN -> Leave unconnected
 *   MAX98357A SD   -> Leave unconnected
 *   Speaker +/-    -> Amp screw terminals
 * 
 * Result:
 *   Generates a pleasant repeating chime melody (A4 440Hz -> E5 659Hz -> A5 880Hz)
 *   No Wi-Fi or server needed.
 */

#include <Arduino.h>
#include "driver/i2s.h"
#include <math.h>

#define I2S_SPK_BCLK 1
#define I2S_SPK_LRC  14
#define I2S_SPK_DIN  21
#define SAMPLE_RATE  16000

void initSpeaker() {
    i2s_config_t i2s_config = {
        .mode = (i2s_mode_t)(I2S_MODE_MASTER | I2S_MODE_TX),
        .sample_rate = SAMPLE_RATE,
        .bits_per_sample = I2S_BITS_PER_SAMPLE_16BIT,
        .channel_format = I2S_CHANNEL_FMT_RIGHT_LEFT,
        .communication_format = i2s_comm_format_t(I2S_COMM_FORMAT_STAND_I2S),
        .intr_alloc_flags = ESP_INTR_FLAG_LEVEL1,
        .dma_buf_count = 8,
        .dma_buf_len = 256,
        .use_apll = false,
        .tx_desc_auto_clear = true
    };

    i2s_pin_config_t pin_config = {
        .bck_io_num = I2S_SPK_BCLK,
        .ws_io_num = I2S_SPK_LRC,
        .data_out_num = I2S_SPK_DIN,
        .data_in_num = I2S_PIN_NO_CHANGE
    };

    i2s_driver_install(I2S_NUM_1, &i2s_config, 0, NULL);
    i2s_set_pin(I2S_NUM_1, &pin_config);
    Serial.println("[Speaker Test] MAX98357A I2S initialized on pins BCLK:1, LRC:14, DIN:21");
}

void playTone(float frequency, int durationMs, float volume = 0.3) {
    int totalSamples = (SAMPLE_RATE * durationMs) / 1000;
    int16_t buffer[256 * 2]; // Stereo (L + R)
    size_t bytes_written;

    int samplesLeft = totalSamples;
    int sampleIndex = 0;

    while (samplesLeft > 0) {
        int chunk = min(256, samplesLeft);
        for (int i = 0; i < chunk; i++) {
            float t = (float)(sampleIndex++) / SAMPLE_RATE;
            int16_t sample = (int16_t)(sin(2 * M_PI * frequency * t) * (32767 * volume));
            buffer[i * 2] = sample;     // Left
            buffer[i * 2 + 1] = sample; // Right
        }
        i2s_write(I2S_NUM_1, buffer, chunk * 4, &bytes_written, portMAX_DELAY);
        samplesLeft -= chunk;
    }
}

void setup() {
    Serial.begin(115200);
    delay(1000);
    Serial.println("\n========================================");
    Serial.println("  TEST 1: MAX98357A SPEAKER & AMP TEST   ");
    Serial.println("========================================");

    initSpeaker();
    Serial.println("[Speaker Test] Playing chime melody...");
}

void loop() {
    Serial.println(">> Playing Tone: 440 Hz (Note A4)...");
    playTone(440.0, 300, 0.25);
    delay(100);

    Serial.println(">> Playing Tone: 659 Hz (Note E5)...");
    playTone(659.25, 300, 0.25);
    delay(100);

    Serial.println(">> Playing Tone: 880 Hz (Note A5)...");
    playTone(880.0, 500, 0.25);
    
    Serial.println("[Speaker Test] Chime complete. Pausing 2 seconds...\n");
    delay(2000);
}
