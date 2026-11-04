/**
 * IVIA Humanoid Companion - Standalone Audio Node
 * Hardware: ESP32-S3 DevKit N16R8 + INMP441 Mic + MAX98357A Amp
 * 
 * In Arduino IDE Tools Menu:
 *   - Board: "ESP32S3 Dev Module"
 *   - USB CDC On Boot: "Disabled"
 *   - PSRAM: "Disabled"
 *   - Flash Mode: "QIO 80MHz" (or "DIO 80MHz")
 *   - Flash Size: "16MB (128Mb)"
 *   - Upload Speed: "921600"
 */

#include <WiFi.h>
#include <WiFiMulti.h>
#include <WebSocketsClient.h>
#include <ArduinoJson.h>
#include "driver/i2s.h"
#include "config.h"

WiFiMulti wifiMulti;
WebSocketsClient webSocket;

bool isConnectedToServer = false;
volatile bool isSpeaking = false;
SemaphoreHandle_t wsMutex = NULL;

// ========================================================
// 1. I2S Microphone Initialization (INMP441)
// ========================================================
void initI2SMicrophone() {
    i2s_config_t mic_config = {
        .mode = (i2s_mode_t)(I2S_MODE_MASTER | I2S_MODE_RX),
        .sample_rate = SAMPLE_RATE,
        .bits_per_sample = I2S_BITS_PER_SAMPLE_32BIT,
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

// ========================================================
// 2. I2S Speaker Initialization (MAX98357A)
// ========================================================
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
// 3. Play Audio Chunk (Mono -> Stereo Expansion)
// ========================================================
void playAudioChunk(uint8_t *payload, size_t length) {
    if (length == 0 || !isSpeaking) return;

    size_t samples = length / 2; // 16-bit mono = 2 bytes per sample
    int16_t *mono_samples = (int16_t*)payload;
    static int16_t stereo_buf[512 * 2];
    size_t chunk_samples = 512;

    for (size_t i = 0; i < samples; i += chunk_samples) {
        if (!isSpeaking) break; // Exit immediately if playback interrupted
        size_t count = min(chunk_samples, samples - i);
        for (size_t j = 0; j < count; j++) {
            int16_t s = mono_samples[i + j];
            stereo_buf[j * 2] = s;     // Left
            stereo_buf[j * 2 + 1] = s; // Right
        }
        size_t bytes_written = 0;
        // Low-latency non-blocking write timeout (20ms) to ensure WebSockets network loop never starves
        i2s_write(I2S_NUM_1, stereo_buf, count * 4, &bytes_written, pdMS_TO_TICKS(20));
    }
}

// ========================================================
// 4. WebSocket Event Handler
// ========================================================
void webSocketEvent(WStype_t type, uint8_t * payload, size_t length) {
    switch(type) {
        case WStype_DISCONNECTED:
            isConnectedToServer = false;
            Serial.println("[WS] Disconnected from Brain Server. Retrying in background... (Note: Render Cloud takes ~30s if waking up)");
            break;

        case WStype_CONNECTED:
            isConnectedToServer = true;
            Serial.printf("[WS] Connected to Server at %s:%d\n", SERVER_HOST, SERVER_PORT);
            webSocket.sendTXT("{\"client\":\"esp32_s3_voice\",\"board\":\"DevKit_N16R8\",\"status\":\"ready\"}");
            break;

        case WStype_TEXT: {
            StaticJsonDocument<256> doc;
            DeserializationError error = deserializeJson(doc, payload, length);
            if (!error) {
                const char* event = doc["event"];
                if (event && strcmp(event, "speaking_start") == 0) {
                    isSpeaking = true;
                    Serial.println("[IVIA] Speaking...");
                } else if (event && strcmp(event, "speaking_end") == 0) {
                    isSpeaking = false;
                    Serial.println("[IVIA] Done speaking.");
                } else if (event && strcmp(event, "stop_speaking") == 0) {
                    isSpeaking = false;
                    i2s_zero_dma_buffer(I2S_NUM_1);
                    Serial.println("[IVIA] Playback interrupted.");
                }
            }
            break;
        }

        case WStype_BIN:
            if (!isSpeaking) isSpeaking = true;
            playAudioChunk(payload, length);
            break;

        default:
            break;
    }
}

// ========================================================
// 5. Continuous Mic Streaming Task (Core 0)
// Batched to 512 samples (32ms) to eliminate TLS buffer saturation
// ========================================================
void micStreamingTask(void *param) {
    int32_t raw_buffer[512];
    int16_t pcm16_buffer[512];
    size_t bytes_read = 0;
    unsigned long lastLog = 0;

    while (true) {
        // Echo prevention: only record when connected and IVIA is NOT speaking
        if (isConnectedToServer && !isSpeaking) {
            esp_err_t res = i2s_read(I2S_NUM_0, raw_buffer, sizeof(raw_buffer), &bytes_read, pdMS_TO_TICKS(50));
            if (res == ESP_OK && bytes_read > 0) {
                size_t samples = bytes_read / sizeof(int32_t);
                int16_t peak = 0;

                // INMP441 returns 24-bit in 32-bit slot -> shift 14 for optimal voice volume (+6dB)
                for (size_t i = 0; i < samples; i++) {
                    int32_t val = raw_buffer[i] >> 14;
                    if (val > 32767) val = 32767;
                    else if (val < -32768) val = -32768;
                    pcm16_buffer[i] = (int16_t)val;
                    int16_t abs_s = abs((int16_t)val);
                    if (abs_s > peak) peak = abs_s;
                }

                if (millis() - lastLog > 3000) {
                    lastLog = millis();
                    Serial.printf("[Mic] Streaming Active (Peak: %d)\n", peak);
                }

                if (wsMutex && xSemaphoreTake(wsMutex, pdMS_TO_TICKS(20)) == pdTRUE) {
                    webSocket.sendBIN((uint8_t*)pcm16_buffer, samples * sizeof(int16_t));
                    xSemaphoreGive(wsMutex);
                }
            }
        } else {
            vTaskDelay(pdMS_TO_TICKS(10));
        }
    }
}

// ========================================================
// 6. Setup & Main Loop
// ========================================================
void setup() {
    delay(1000);
    Serial.begin(115200);
    delay(500);

    Serial.println("\n=============================================");
    Serial.println("  IVIA Companion - Standalone Audio Node     ");
    Serial.println("     ESP32-S3 DevKit-N16R8 (Mic + Speaker)   ");
    Serial.println("=============================================");

    wsMutex = xSemaphoreCreateMutex();

    if (psramFound()) {
        Serial.printf("[System] PSRAM Detected: %d bytes free\n", ESP.getFreePsram());
    } else {
        Serial.printf("[System] Internal SRAM: %d bytes free\n", ESP.getFreeHeap());
    }

    initI2SMicrophone();
    initI2SSpeaker();

    // Connect to Wi-Fi (Multi-AP Automatic Roaming)
    WiFi.mode(WIFI_STA);
    WiFi.setSleep(false); // Permanently disable modem sleep for uninterrupted connection

    wifiMulti.addAP(WIFI_SSID_1, WIFI_PASSWORD_1);
    if (strlen(WIFI_SSID_2) > 0) {
        wifiMulti.addAP(WIFI_SSID_2, WIFI_PASSWORD_2);
    }

    Serial.println("[Wi-Fi] Scanning and connecting to available network...");
    int attempts = 0;
    while (wifiMulti.run() != WL_CONNECTED && attempts < 30) {
        delay(500);
        Serial.print(".");
        attempts++;
    }

    if (WiFi.status() == WL_CONNECTED) {
        WiFi.setSleep(false);
        Serial.println("\n[Wi-Fi] Connected!");
        Serial.printf("[Wi-Fi] Connected to: %s\n", WiFi.SSID().c_str());
        Serial.print("[Wi-Fi] IP Address: ");
        Serial.println(WiFi.localIP());

        // Sync system clock via NTP (Required so SSL/TLS certificates pass date validation)
        Serial.print("[NTP] Syncing clock for SSL");
        configTime(0, 0, "pool.ntp.org", "time.google.com");
        time_t now = time(nullptr);
        int ntpWait = 0;
        while (now < 1700000000 && ntpWait < 20) { // Year > Nov 2023
            delay(250);
            Serial.print(".");
            now = time(nullptr);
            ntpWait++;
        }
        Serial.println(" Synced!");
    } else {
        Serial.println("\n[Wi-Fi] Still looking for network. Retrying in background...");
    }

    // Connect to Python Brain Server (Cloud WSS or Local WS)
#if USE_SSL
    webSocket.beginSSL(SERVER_HOST, SERVER_PORT, WS_PATH);
    Serial.printf("[WS] Connecting securely (WSS) to https://%s:%d%s\n", SERVER_HOST, SERVER_PORT, WS_PATH);
#else
    webSocket.begin(SERVER_HOST, SERVER_PORT, WS_PATH);
    Serial.printf("[WS] Connecting (WS) to http://%s:%d%s\n", SERVER_HOST, SERVER_PORT, WS_PATH);
#endif
    webSocket.onEvent(webSocketEvent);
    webSocket.setReconnectInterval(3000); // Built-in smooth reconnection retry
    // Keep-alive heartbeat: ping every 15s to keep Render Cloud proxy and Hotspot NAT alive
    webSocket.enableHeartbeat(15000, 4000, 2);

    // Launch microphone task on Core 0
    xTaskCreatePinnedToCore(
        micStreamingTask,
        "MicTask",
        8192,
        NULL,
        1,
        NULL,
        0
    );

    Serial.println("[System] Audio Node Online & Ready!");
}

void loop() {
    // 1. Maintain Wi-Fi connection with auto-reconnect
    if (wifiMulti.run() != WL_CONNECTED) {
        delay(10);
        return;
    }

    // 2. Drive WebSocket networking engine
    if (wsMutex && xSemaphoreTake(wsMutex, pdMS_TO_TICKS(10)) == pdTRUE) {
        webSocket.loop();
        xSemaphoreGive(wsMutex);
    }

    delay(2);
}
