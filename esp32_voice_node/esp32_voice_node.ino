/**
 * IVIA Humanoid Companion - ESP32 Voice Assistant Node
 * Autonomous Humanoid Companion Node
 * 
 * Hardware:
 *  - ESP32 Dev Module (WROOM-32)
 *  - INMP441 I2S Digital Microphone (Audio Input)
 *  - MAX98357A I2S Class-D Amplifier + Speaker (Audio Output)
 * 
 * Required Arduino Libraries:
 *  - WebSockets by Markus Sattler (install via Arduino Library Manager)
 *  - ArduinoJson by Benoit Blanchon (install via Arduino Library Manager)
 *  - WiFi (Built-in ESP32)
 */

#include <WiFi.h>
#include <WebSocketsClient.h>
#include <ArduinoJson.h>
#include "driver/i2s.h"
#include "config.h"

// WebSockets Client
WebSocketsClient webSocket;

// State tracking
bool isConnectedToServer = false;
bool isSpeaking = false;      // True when robot speaker is playing audio
bool isRecording = false;     // True when microphone is streaming
unsigned long lastStatusPing = 0;

// ========================================================
// I2S Configuration Functions
// ========================================================

/**
 * Configure I2S_NUM_0 for INMP441 Microphone (Audio In)
 */
void initI2SMicrophone() {
    i2s_config_t i2s_mic_config = {
        .mode = (i2s_mode_t)(I2S_MODE_MASTER | I2S_MODE_RX),
        .sample_rate = SAMPLE_RATE,
        .bits_per_sample = I2S_BITS_PER_SAMPLE_32BIT, // INMP441 outputs 24-bit in 32-bit slot
        .channel_format = I2S_CHANNEL_FMT_ONLY_LEFT,  // L/R tied to GND -> Left
        .communication_format = i2s_comm_format_t(I2S_COMM_FORMAT_STAND_I2S),
        .intr_alloc_flags = ESP_INTR_FLAG_LEVEL1,
        .dma_buf_count = 8,
        .dma_buf_len = 512,
        .use_apll = false,
        .tx_desc_auto_clear = false,
        .fixed_mclk = 0
    };

    i2s_pin_config_t mic_pins = {
        .bck_io_num = I2S_MIC_SCK,
        .ws_io_num = I2S_MIC_WS,
        .data_out_num = I2S_PIN_NO_CHANGE,
        .data_in_num = I2S_MIC_SD
    };

    esp_err_t err = i2s_driver_install(I2S_NUM_0, &i2s_mic_config, 0, NULL);
    if (err != ESP_OK) {
        Serial.printf("[I2S MIC] Failed to install driver: %d\n", err);
        return;
    }

    err = i2s_set_pin(I2S_NUM_0, &mic_pins);
    if (err != ESP_OK) {
        Serial.printf("[I2S MIC] Failed to set pins: %d\n", err);
        return;
    }

    Serial.println("[I2S MIC] INMP441 initialized successfully.");
}

/**
 * Configure I2S_NUM_1 for MAX98357A Amplifier (Audio Out)
 */
void initI2SSpeaker() {
    i2s_config_t i2s_spk_config = {
        .mode = (i2s_mode_t)(I2S_MODE_MASTER | I2S_MODE_TX),
        .sample_rate = SAMPLE_RATE,
        .bits_per_sample = I2S_BITS_PER_SAMPLE_16BIT,
        .channel_format = I2S_CHANNEL_FMT_RIGHT_LEFT, // Stereo output (plays on mono amp cleanly)
        .communication_format = i2s_comm_format_t(I2S_COMM_FORMAT_STAND_I2S),
        .intr_alloc_flags = ESP_INTR_FLAG_LEVEL1,
        .dma_buf_count = 8,
        .dma_buf_len = 512,
        .use_apll = false,
        .tx_desc_auto_clear = true,
        .fixed_mclk = 0
    };

    i2s_pin_config_t spk_pins = {
        .bck_io_num = I2S_SPK_BCLK,
        .ws_io_num = I2S_SPK_LRC,
        .data_out_num = I2S_SPK_DIN,
        .data_in_num = I2S_PIN_NO_CHANGE
    };

    esp_err_t err = i2s_driver_install(I2S_NUM_1, &i2s_spk_config, 0, NULL);
    if (err != ESP_OK) {
        Serial.printf("[I2S SPK] Failed to install driver: %d\n", err);
        return;
    }

    err = i2s_set_pin(I2S_NUM_1, &spk_pins);
    if (err != ESP_OK) {
        Serial.printf("[I2S SPK] Failed to set pins: %d\n", err);
        return;
    }

    Serial.println("[I2S SPK] MAX98357A initialized successfully.");
}

// ========================================================
// Audio Playback Task (Receives Audio from Server)
// ========================================================
void playAudioChunk(uint8_t *payload, size_t length) {
    if (length == 0) return;

    // The server streams 16-bit mono PCM. We expand mono to stereo for MAX98357A
    size_t samples = length / 2; // 2 bytes per 16-bit sample
    int16_t *mono_samples = (int16_t*)payload;
    
    // Static buffer to avoid reallocation
    static int16_t stereo_buf[1024]; 
    size_t chunk_samples = 512; // 512 stereo samples (1024 int16)

    for (size_t i = 0; i < samples; i += chunk_samples) {
        size_t count = min(chunk_samples, samples - i);
        for (size_t j = 0; j < count; j++) {
            int16_t s = mono_samples[i + j];
            stereo_buf[j * 2] = s;     // Left
            stereo_buf[j * 2 + 1] = s; // Right
        }
        size_t bytes_written = 0;
        i2s_write(I2S_NUM_1, stereo_buf, count * 4, &bytes_written, portMAX_DELAY);
    }
}

// ========================================================
// WebSocket Event Handler
// ========================================================
void webSocketEvent(WStype_t type, uint8_t * payload, size_t length) {
    switch(type) {
        case WStype_DISCONNECTED:
            isConnectedToServer = false;
            Serial.println("[WS] Disconnected from server");
            break;

        case WStype_CONNECTED:
            isConnectedToServer = true;
            Serial.printf("[WS] Connected to IVIA Brain Server at %s:%d\n", SERVER_HOST, SERVER_PORT);
            // Send client handshake
            webSocket.sendTXT("{\"client\":\"esp32_voice\",\"status\":\"ready\"}");
            break;

        case WStype_TEXT: {
            // Text JSON message from server (e.g. control signals)
            StaticJsonDocument<256> doc;
            DeserializationError error = deserializeJson(doc, payload, length);
            if (!error) {
                const char* event = doc["event"];
                if (event && strcmp(event, "speaking_start") == 0) {
                    isSpeaking = true;
                    Serial.println("[IVIA] Started Speaking...");
                } else if (event && strcmp(event, "speaking_end") == 0) {
                    isSpeaking = false;
                    Serial.println("[IVIA] Finished Speaking.");
                }
            }
            break;
        }

        case WStype_BIN:
            // Binary audio chunk received from TTS engine
            isSpeaking = true;
            playAudioChunk(payload, length);
            break;

        case WStype_ERROR:
            Serial.printf("[WS] Error occurred\n");
            break;

        default:
            break;
    }
}

// ========================================================
// Audio Recording & Streaming Task
// ========================================================
void micStreamingTask(void *param) {
    // 32-bit buffer for INMP441 raw read
    int32_t raw_buffer[256];
    // 16-bit buffer for downsampled audio
    int16_t pcm16_buffer[256];
    size_t bytes_read = 0;

    while (true) {
        // Echo prevention: only record when connected and IVIA is NOT speaking
        bool shouldRecord = isConnectedToServer && !isSpeaking;

        if (shouldRecord) {
            esp_err_t result = i2s_read(I2S_NUM_0, raw_buffer, sizeof(raw_buffer), &bytes_read, pdMS_TO_TICKS(50));
            if (result == ESP_OK && bytes_read > 0) {
                size_t samples_read = bytes_read / sizeof(int32_t);

                // Convert 24/32-bit INMP441 data to 16-bit PCM with clamping
                for (size_t i = 0; i < samples_read; i++) {
                    int32_t val = raw_buffer[i] >> 15;
                    if (val > 32767) val = 32767;
                    else if (val < -32768) val = -32768;
                    pcm16_buffer[i] = (int16_t)val;
                }

                // Send 16-bit PCM packet to server over WebSocket
                webSocket.sendBIN((uint8_t*)pcm16_buffer, samples_read * sizeof(int16_t));
            }
        } else {
            vTaskDelay(pdMS_TO_TICKS(10));
        }
    }
}

// ========================================================
// Setup & Main Loop
// ========================================================
void setup() {
    Serial.begin(115200);
    delay(1000);

    Serial.println("\n=============================================");
    Serial.println("  IVIA Humanoid Companion - Voice Node       ");
    Serial.println("         Autonomous Voice Node               ");
    Serial.println("=============================================");

    // Initialize I2S Audio Hardware

    // Initialize I2S Audio Hardware
    initI2SMicrophone();
    initI2SSpeaker();

    // Connect to Wi-Fi
    Serial.printf("[Wi-Fi] Connecting to %s...\n", WIFI_SSID);
    WiFi.mode(WIFI_STA);
    WiFi.begin(WIFI_SSID, WIFI_PASSWORD);

    int attempts = 0;
    while (WiFi.status() != WL_CONNECTED && attempts < 40) {
        delay(500);
        Serial.print(".");
        attempts++;
    }

    if (WiFi.status() == WL_CONNECTED) {
        Serial.println("\n[Wi-Fi] Connected!");
        Serial.printf("[Wi-Fi] ESP32 IP: %s\n", WiFi.localIP().toString().c_str());
    } else {
        Serial.println("\n[Wi-Fi] Connection failed. Retrying in loop...");
    }

    // Configure WebSockets Client
    webSocket.begin(SERVER_HOST, SERVER_PORT, WS_PATH);
    webSocket.onEvent(webSocketEvent);
    webSocket.setReconnectInterval(3000);

    // Launch Microphone Streaming Task on Core 0 (leaving Core 1 for WebSockets/Wi-Fi)
    xTaskCreatePinnedToCore(
        micStreamingTask,
        "MicTask",
        4096,
        NULL,
        1,
        NULL,
        0
    );

    Serial.println("[System] Voice Node Ready!");
}

void loop() {
    // Keep WebSocket connection alive
    webSocket.loop();

    // Reconnect Wi-Fi if dropped
    if (WiFi.status() != WL_CONNECTED) {
        static unsigned long lastWifiRetry = 0;
        if (millis() - lastWifiRetry > 5000) {
            lastWifiRetry = millis();
            Serial.println("[Wi-Fi] Reconnecting...");
            WiFi.reconnect();
        }
    }
}
