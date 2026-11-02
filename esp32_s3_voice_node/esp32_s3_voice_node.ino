/**
 * IVIA Humanoid Companion - Single ESP32-S3 Voice Node
 * Autonomous Humanoid Companion Node
 * 
 * Hardware:
 *   - ESP32-S3 N16R8 (16MB Flash, 8MB PSRAM)
 *   - INMP441 Microphone (I2S_NUM_0): SCK=41, WS=42, SD=2
 *   - MAX98357A Amplifier (I2S_NUM_1): BCLK=1, LRC=14, DIN=21
 * 
 * In Arduino IDE Tools Menu:
 *   - Board: "ESP32S3 Dev Module"
 *   - PSRAM: "OPI PSRAM"
 *   - Flash Size: "16MB"
 *   - USB CDC On Boot: "Enabled"
 */

#include <WiFi.h>
#include <WebSocketsClient.h>
#include <ArduinoJson.h>
#include "driver/i2s.h"
#include "config.h"

WebSocketsClient webSocket;

// State flags
bool isConnectedToServer = false;
volatile bool isSpeaking = false;     // True when robot speaker is playing audio
volatile unsigned long lastAudioTime = 0;
bool isRecording = false;
SemaphoreHandle_t wsMutex = NULL;

// ========================================================
// I2S Hardware Initialization
// ========================================================

void initI2SMicrophone() {
    i2s_config_t mic_config = {
        .mode = (i2s_mode_t)(I2S_MODE_MASTER | I2S_MODE_RX),
        .sample_rate = SAMPLE_RATE,
        .bits_per_sample = I2S_BITS_PER_SAMPLE_32BIT, // INMP441 24-bit in 32-bit slot
        .channel_format = I2S_CHANNEL_FMT_ONLY_LEFT,
        .communication_format = i2s_comm_format_t(I2S_COMM_FORMAT_STAND_I2S),
        .intr_alloc_flags = ESP_INTR_FLAG_LEVEL1,
        .dma_buf_count = 8,
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

    esp_err_t err = i2s_driver_install(I2S_NUM_0, &mic_config, 0, NULL);
    if (err != ESP_OK) {
        Serial.printf("[I2S MIC] Driver install failed: %d\n", err);
        return;
    }

    err = i2s_set_pin(I2S_NUM_0, &mic_pins);
    if (err != ESP_OK) {
        Serial.printf("[I2S MIC] Set pin failed: %d\n", err);
        return;
    }

    Serial.println("[I2S MIC] INMP441 initialized on pins SCK:41, WS:42, SD:2");
}

void initI2SSpeaker() {
    i2s_config_t spk_config = {
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

    i2s_pin_config_t spk_pins = {
        .bck_io_num = I2S_SPK_BCLK,
        .ws_io_num = I2S_SPK_LRC,
        .data_out_num = I2S_SPK_DIN,
        .data_in_num = I2S_PIN_NO_CHANGE
    };

    esp_err_t err = i2s_driver_install(I2S_NUM_1, &spk_config, 0, NULL);
    if (err != ESP_OK) {
        Serial.printf("[I2S SPK] Driver install failed: %d\n", err);
        return;
    }

    err = i2s_set_pin(I2S_NUM_1, &spk_pins);
    if (err != ESP_OK) {
        Serial.printf("[I2S SPK] Set pin failed: %d\n", err);
        return;
    }

    Serial.println("[I2S SPK] MAX98357A initialized on pins BCLK:1, LRC:14, DIN:21");
}

// ========================================================
// Playback Audio Chunk (Mono -> Stereo Expansion)
// ========================================================
void playAudioChunk(uint8_t *payload, size_t length) {
    if (length == 0 || !isSpeaking) return;

    size_t samples = length / 2; // 16-bit mono = 2 bytes per sample
    int16_t *mono_samples = (int16_t*)payload;
    
    static int16_t stereo_buf[512 * 2];
    size_t chunk_samples = 512;

    for (size_t i = 0; i < samples; i += chunk_samples) {
        if (!isSpeaking) break; // Exit immediately if interrupted!
        size_t count = min(chunk_samples, samples - i);
        for (size_t j = 0; j < count; j++) {
            int16_t s = mono_samples[i + j];
            stereo_buf[j * 2] = s;     // Left channel
            stereo_buf[j * 2 + 1] = s; // Right channel
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
            Serial.println("[WS] Disconnected from IVIA Brain Server");
            break;

        case WStype_CONNECTED:
            isConnectedToServer = true;
            Serial.printf("[WS] Connected to IVIA Brain Server at %s:%d\n", SERVER_HOST, SERVER_PORT);
            webSocket.sendTXT("{\"client\":\"esp32_s3_voice\",\"board\":\"N16R8\",\"status\":\"ready\"}");
            break;

        case WStype_TEXT: {
            StaticJsonDocument<256> doc;
            DeserializationError error = deserializeJson(doc, payload, length);
            if (!error) {
                const char* event = doc["event"];
                if (event && strcmp(event, "speaking_start") == 0) {
                    isSpeaking = true;
                    lastAudioTime = millis();
                    Serial.println("[IVIA] Speaking...");
                } else if (event && strcmp(event, "speaking_end") == 0) {
                    isSpeaking = false;
                    Serial.println("[IVIA] Finished Speaking.");
                }
            }
            break;
        }

        case WStype_BIN:
            if (!isSpeaking) isSpeaking = true;
            lastAudioTime = millis();
            playAudioChunk(payload, length);
            lastAudioTime = millis();
            break;

        default:
            break;
    }
}

// ========================================================
// Microphone Recording Task (Pinned to Core 0)
// ========================================================
void micStreamingTask(void *param) {
    int32_t raw_buffer[256];
    int16_t pcm16_buffer[256];
    size_t bytes_read = 0;
    unsigned long lastMicLog = 0;

    while (true) {
        // Echo prevention: only record when connected and IVIA is NOT speaking
        // This ensures the speaker plays 100% cleanly without self-feedback or interruption
        bool shouldRecord = isConnectedToServer && !isSpeaking;

        if (shouldRecord) {
            esp_err_t result = i2s_read(I2S_NUM_0, raw_buffer, sizeof(raw_buffer), &bytes_read, pdMS_TO_TICKS(50));
            if (result == ESP_OK && bytes_read > 0) {
                size_t samples = bytes_read / sizeof(int32_t);
                int16_t peak = 0;

                // Convert 32-bit INMP441 sample to clean 16-bit PCM with optimal +6dB voice gain
                for (size_t i = 0; i < samples; i++) {
                    int32_t val = raw_buffer[i] >> 14;
                    if (val > 32767) val = 32767;
                    else if (val < -32768) val = -32768;

                    pcm16_buffer[i] = (int16_t)val;
                    int16_t abs_s = abs((int16_t)val);
                    if (abs_s > peak) peak = abs_s;
                }

                // Log mic sound detection to Serial Monitor every 3 seconds
                if (millis() - lastMicLog > 3000) {
                    lastMicLog = millis();
                    Serial.printf("[Mic] Streaming active (Peak: %d)\n", peak);
                }

                // Send PCM binary chunk to server with thread-safe mutex
                if (wsMutex && xSemaphoreTake(wsMutex, pdMS_TO_TICKS(20)) == pdTRUE) {
                    webSocket.sendBIN((uint8_t*)pcm16_buffer, samples * sizeof(int16_t));
                    xSemaphoreGive(wsMutex);
                } else if (!wsMutex) {
                    webSocket.sendBIN((uint8_t*)pcm16_buffer, samples * sizeof(int16_t));
                }
            }
        } else {
            vTaskDelay(pdMS_TO_TICKS(10));
        }
    }
}

// ========================================================
// Setup & Loop
// ========================================================
void setup() {
    Serial.begin(115200);
    delay(1000);

    Serial.println("\n=============================================");
    Serial.println("  IVIA Companion - ESP32-S3 Voice Node       ");
    Serial.println("         Autonomous Voice Node               ");
    Serial.println("=============================================");

    wsMutex = xSemaphoreCreateMutex();

    if (psramFound()) {
        Serial.printf("[System] PSRAM detected: %d bytes free\n", ESP.getFreePsram());
    }

    // Initialize Audio I2S Peripherals
    initI2SMicrophone();
    initI2SSpeaker();

    // Connect to Wi-Fi
    Serial.printf("[Wi-Fi] Connecting to %s", WIFI_SSID);
    WiFi.mode(WIFI_STA);
    WiFi.begin(WIFI_SSID, WIFI_PASSWORD);

    int attempts = 0;
    while (WiFi.status() != WL_CONNECTED && attempts < 40) {
        delay(500);
        Serial.print(".");
        attempts++;
    }

    if (WiFi.status() == WL_CONNECTED) {
        WiFi.setSleep(false); // Disable modem sleep to prevent packet drops and audio latency spikes
        Serial.println("\n[Wi-Fi] Connected!");
        Serial.printf("[Wi-Fi] IP Address: %s\n", WiFi.localIP().toString().c_str());
    } else {
        Serial.println("\n[Wi-Fi] Connection pending. Retrying in background...");
    }

    // Initialize WebSockets Client (Cloud WSS or Local WS)
#if USE_SSL
    webSocket.beginSSL(SERVER_HOST, SERVER_PORT, WS_PATH);
    Serial.printf("[WS] Connecting securely (WSS) to https://%s:%d%s\n", SERVER_HOST, SERVER_PORT, WS_PATH);
#else
    webSocket.begin(SERVER_HOST, SERVER_PORT, WS_PATH);
    Serial.printf("[WS] Connecting (WS) to http://%s:%d%s\n", SERVER_HOST, SERVER_PORT, WS_PATH);
#endif
    webSocket.onEvent(webSocketEvent);
    webSocket.setReconnectInterval(3000);

    // Launch Microphone Streaming Task on Core 0
    xTaskCreatePinnedToCore(
        micStreamingTask,
        "MicTask",
        8192,
        NULL,
        1,
        NULL,
        0
    );

    Serial.println("[System] ESP32-S3 Voice Node Ready!");
}

void loop() {
    if (wsMutex && xSemaphoreTake(wsMutex, pdMS_TO_TICKS(10)) == pdTRUE) {
        webSocket.loop();
        xSemaphoreGive(wsMutex);
    } else if (!wsMutex) {
        webSocket.loop();
    }

    if (WiFi.status() != WL_CONNECTED) {
        static unsigned long lastWifiRetry = 0;
        if (millis() - lastWifiRetry > 5000) {
            lastWifiRetry = millis();
            Serial.println("[Wi-Fi] Reconnecting...");
            WiFi.reconnect();
        }
    }
}
