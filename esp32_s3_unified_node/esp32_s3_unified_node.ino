/**
 * IVIA Humanoid Companion - ESP32-S3 Unified Node
 * COMBINED: Voice Assistant (I2S Mic + Speaker) + Live OV3660 Camera Server
 * Autonomous Humanoid Companion Node
 * 
 * Hardware:
 *   - ESP32-S3 N16R8 (16MB Flash, 8MB PSRAM)
 *   - INMP441 Microphone (I2S_NUM_0): SCK=41, WS=42, SD=2
 *   - MAX98357A Amplifier (I2S_NUM_1): BCLK=1, LRC=14, DIN=21
 *   - OV3660 Camera Sensor (PSRAM Framebuffers): Pins 4,5,6,7,8,9,10,11,12,13,15,16,17,18
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
#include "esp_camera.h"
#include "esp_http_server.h"
#include "driver/i2s.h"
#include "config.h"

WebSocketsClient webSocket;
httpd_handle_t stream_httpd = NULL;

// State flags
bool isConnectedToServer = false;
volatile bool isSpeaking = false;
volatile unsigned long lastAudioTime = 0;
bool cameraInitialized = false;
esp_err_t cameraInitError = ESP_OK;
SemaphoreHandle_t wsMutex = NULL;
SemaphoreHandle_t cameraMutex = NULL;

// ========================================================
// 1. Camera HTTP Streaming Handlers
// ========================================================
static esp_err_t capture_handler(httpd_req_t *req) {
    if (!cameraInitialized) {
        httpd_resp_set_status(req, "503 Service Unavailable");
        httpd_resp_set_type(req, "application/json");
        httpd_resp_set_hdr(req, "Access-Control-Allow-Origin", "*");
        char errBuf[128];
        snprintf(errBuf, sizeof(errBuf), "{\"error\":\"Camera hardware not initialized\",\"code\":\"0x%x\"}", cameraInitError);
        return httpd_resp_send(req, errBuf, HTTPD_RESP_USE_STRLEN);
    }

    if (cameraMutex && xSemaphoreTake(cameraMutex, pdMS_TO_TICKS(1500)) != pdTRUE) {
        Serial.println("[Camera] Capture mutex timeout");
        httpd_resp_send_500(req);
        return ESP_FAIL;
    }

    camera_fb_t * fb = esp_camera_fb_get();
    if (!fb || fb->len == 0) {
        if (fb) esp_camera_fb_return(fb);
        if (cameraMutex) xSemaphoreGive(cameraMutex);
        Serial.println("[Camera] Capture failed: invalid or NULL frame buffer");
        httpd_resp_send_500(req);
        return ESP_FAIL;
    }
    httpd_resp_set_type(req, "image/jpeg");
    httpd_resp_set_hdr(req, "Content-Disposition", "inline; filename=capture.jpg");
    httpd_resp_set_hdr(req, "Access-Control-Allow-Origin", "*");
    httpd_resp_set_hdr(req, "Cache-Control", "no-cache, no-store, must-revalidate");
    esp_err_t res = httpd_resp_send(req, (const char *)fb->buf, fb->len);
    esp_camera_fb_return(fb);

    if (cameraMutex) xSemaphoreGive(cameraMutex);
    return res;
}

static esp_err_t stream_handler(httpd_req_t *req) {
    camera_fb_t * fb = NULL;
    esp_err_t res = ESP_OK;
    char part_buf[64];

    static const char* _STREAM_CONTENT_TYPE = "multipart/x-mixed-replace;boundary=123456789000000000000987654321";
    static const char* _STREAM_BOUNDARY = "\r\n--123456789000000000000987654321\r\n";
    static const char* _STREAM_PART = "Content-Type: image/jpeg\r\nContent-Length: %u\r\n\r\n";

    res = httpd_resp_set_type(req, _STREAM_CONTENT_TYPE);
    httpd_resp_set_hdr(req, "Access-Control-Allow-Origin", "*");
    httpd_resp_set_hdr(req, "Cache-Control", "no-cache, no-store, must-revalidate");
    if (res != ESP_OK) return res;

    while (true) {
        if (cameraMutex && xSemaphoreTake(cameraMutex, pdMS_TO_TICKS(500)) == pdTRUE) {
            fb = esp_camera_fb_get();
            if (!fb || fb->len == 0) {
                if (fb) esp_camera_fb_return(fb);
                xSemaphoreGive(cameraMutex);
                vTaskDelay(pdMS_TO_TICKS(10));
                continue;
            }

            size_t hlen = snprintf(part_buf, 64, _STREAM_PART, fb->len);
            res = httpd_resp_send_chunk(req, _STREAM_BOUNDARY, strlen(_STREAM_BOUNDARY));
            if (res == ESP_OK) res = httpd_resp_send_chunk(req, part_buf, hlen);
            if (res == ESP_OK) res = httpd_resp_send_chunk(req, (const char *)fb->buf, fb->len);
            esp_camera_fb_return(fb);
            xSemaphoreGive(cameraMutex);
        } else {
            vTaskDelay(pdMS_TO_TICKS(20));
            continue;
        }

        if (res != ESP_OK) break;
        vTaskDelay(pdMS_TO_TICKS(35)); // Cap stream to ~25 FPS for stability
    }
    return res;
}

// Lightweight HTML Index Page (Does not block server like infinite stream does!)
static esp_err_t index_handler(httpd_req_t *req) {
    httpd_resp_set_type(req, "text/html");
    httpd_resp_set_hdr(req, "Access-Control-Allow-Origin", "*");

    if (!cameraInitialized) {
        char errPage[600];
        snprintf(errPage, sizeof(errPage),
            "<!DOCTYPE html><html><body style='font-family:sans-serif;background:#090d16;color:#f1f5f9;text-align:center;padding:40px;'>"
            "<h1 style='color:#ef4444;'>Camera Sensor Not Detected</h1>"
            "<p>esp_camera_init returned error: <b style='color:#f59e0b;'>0x%x</b></p>"
            "<p style='color:#94a3b8;max-width:500px;margin:15px auto;'>Check that the OV3660 ribbon cable is seated firmly in the FPC connector and that Tools &gt; PSRAM is set to <b>OPI PSRAM</b>.</p>"
            "<p><a href='/status' style='color:#00e5ff;'>View Diagnostic JSON (/status)</a></p>"
            "</body></html>", cameraInitError);
        return httpd_resp_send(req, errPage, HTTPD_RESP_USE_STRLEN);
    }

    static const char INDEX_PAGE[] PROGMEM = 
        "<!DOCTYPE html><html><head><meta charset='UTF-8'><title>IVIA OV3660 Camera Node</title>"
        "<style>body{font-family:sans-serif;background:#090d16;color:#f1f5f9;text-align:center;padding:30px;}"
        "h1{color:#00f59b;}a{color:#00e5ff;text-decoration:none;margin:0 10px;padding:8px 16px;border:1px solid #00e5ff;border-radius:8px;}"
        "img{max-width:90%;border-radius:12px;margin-top:20px;border:2px solid #1e293b;}</style></head>"
        "<body><h1>IVIA - OV3660 Live Node</h1><p>Camera is Online & Ready.</p>"
        "<p><a href='/capture' target='_blank'>Snapshot (/capture)</a><a href='/stream' target='_blank'>Stream (/stream)</a><a href='/status'>Status (/status)</a></p>"
        "<img src='/capture' alt='Camera Snapshot' id='preview'><br><br>"
        "<button onclick=\"document.getElementById('preview').src='/capture?t='+Date.now()\" style='padding:8px 20px;background:#00f59b;border:none;border-radius:8px;cursor:pointer;font-weight:bold;'>Refresh Preview</button>"
        "</body></html>";
    return httpd_resp_send(req, INDEX_PAGE, HTTPD_RESP_USE_STRLEN);
}

// Diagnostic JSON Status Endpoint
static esp_err_t status_handler(httpd_req_t *req) {
    char buf[220];
    snprintf(buf, sizeof(buf), 
        "{\"status\":\"online\",\"camera\":%s,\"camera_err\":\"0x%x\",\"psram_free\":%d,\"heap_free\":%d,\"rssi\":%d}",
        cameraInitialized ? "\"OV3660 OK\"" : "\"NOT DETECTED\"",
        cameraInitError, ESP.getFreePsram(), ESP.getFreeHeap(), WiFi.RSSI());
    httpd_resp_set_type(req, "application/json");
    httpd_resp_set_hdr(req, "Access-Control-Allow-Origin", "*");
    return httpd_resp_send(req, buf, HTTPD_RESP_USE_STRLEN);
}

void startCameraServer() {
    httpd_config_t config = HTTPD_DEFAULT_CONFIG();
    config.server_port = 80;
    config.ctrl_port = 32768;
    config.max_open_sockets = 4;
    config.lru_purge_enable = true;
    config.recv_wait_timeout = 5;
    config.send_wait_timeout = 5;
    config.stack_size = 8192;

    httpd_uri_t index_uri = {
        .uri       = "/",
        .method    = HTTP_GET,
        .handler   = index_handler,
        .user_ctx  = NULL
    };

    httpd_uri_t stream_uri = {
        .uri       = "/stream",
        .method    = HTTP_GET,
        .handler   = stream_handler,
        .user_ctx  = NULL
    };

    httpd_uri_t capture_uri = {
        .uri       = "/capture",
        .method    = HTTP_GET,
        .handler   = capture_handler,
        .user_ctx  = NULL
    };

    httpd_uri_t status_uri = {
        .uri       = "/status",
        .method    = HTTP_GET,
        .handler   = status_handler,
        .user_ctx  = NULL
    };

    if (httpd_start(&stream_httpd, &config) == ESP_OK) {
        httpd_register_uri_handler(stream_httpd, &index_uri);
        httpd_register_uri_handler(stream_httpd, &stream_uri);
        httpd_register_uri_handler(stream_httpd, &capture_uri);
        httpd_register_uri_handler(stream_httpd, &status_uri);
        Serial.println("[Camera] Stream server active on port 80 (endpoints: /, /capture, /stream, /status)");
    }
}

void initOV3660Camera() {
    cameraMutex = xSemaphoreCreateMutex();

    camera_config_t config;
    config.ledc_channel = LEDC_CHANNEL_0;
    config.ledc_timer = LEDC_TIMER_0;
    config.pin_d0 = Y2_GPIO_NUM;
    config.pin_d1 = Y3_GPIO_NUM;
    config.pin_d2 = Y4_GPIO_NUM;
    config.pin_d3 = Y5_GPIO_NUM;
    config.pin_d4 = Y6_GPIO_NUM;
    config.pin_d5 = Y7_GPIO_NUM;
    config.pin_d6 = Y8_GPIO_NUM;
    config.pin_d7 = Y9_GPIO_NUM;
    config.pin_xclk = XCLK_GPIO_NUM;
    config.pin_pclk = PCLK_GPIO_NUM;
    config.pin_vsync = VSYNC_GPIO_NUM;
    config.pin_href = HREF_GPIO_NUM;
    config.pin_sccb_sda = SIOD_GPIO_NUM;
    config.pin_sccb_scl = SIOC_GPIO_NUM;
    config.pin_pwdn = PWDN_GPIO_NUM;
    config.pin_reset = RESET_GPIO_NUM;
    config.xclk_freq_hz = 10000000;         // 10MHz stable pixel clock for OV3660
    config.pixel_format = PIXFORMAT_JPEG;   // Streaming format
    config.grab_mode = CAMERA_GRAB_WHEN_EMPTY; // Only fill buffer when requested (stops FB-OVF spam)

    if (psramFound()) {
        Serial.printf("[Camera] PSRAM detected (%d bytes free). Setting 640x480 dual buffers.\n", ESP.getFreePsram());
        config.frame_size = FRAMESIZE_VGA;      // 640x480
        config.fb_location = CAMERA_FB_IN_PSRAM; // Store frames in 8MB PSRAM!
        config.fb_count = 2;
        config.jpeg_quality = 14;
    } else {
        Serial.println("[Camera] WARNING: PSRAM NOT detected! Falling back to DRAM 320x240.");
        Serial.println("[Camera] ACTION: In Arduino IDE Tools menu, set PSRAM: 'OPI PSRAM'");
        config.frame_size = FRAMESIZE_QVGA;     // 320x240 fallback
        config.fb_location = CAMERA_FB_IN_DRAM;
        config.fb_count = 1;
        config.jpeg_quality = 16;
    }

    cameraInitError = esp_camera_init(&config);
    if (cameraInitError != ESP_OK) {
        Serial.printf("[Camera] CRITICAL: Init failed: 0x%x\n", cameraInitError);
        if (cameraInitError == 0x105) {
            Serial.println("[Camera] Cause: 0x105 = ESP_ERR_NOT_FOUND (Sensor I2C failed).");
            Serial.println("[Camera] ACTION: Re-seat OV3660 ribbon cable into FPC connector firmly with contacts facing PCB!");
        } else if (cameraInitError == 0x101) {
            Serial.println("[Camera] Cause: 0x101 = ESP_ERR_NO_MEM (Out of RAM).");
            Serial.println("[Camera] ACTION: In Tools menu, set PSRAM: 'OPI PSRAM'!");
        }
        cameraInitialized = false;
    } else {
        cameraInitialized = true;
        Serial.println("[Camera] OV3660 initialized with buffers!");

        // Set orientation: Correct upside-down camera mount
        sensor_t * s = esp_camera_sensor_get();
        if (s != NULL) {
            s->set_vflip(s, 1);    // 1 = Flip vertically (right-side up fix)
            s->set_hmirror(s, 1);  // 1 = Mirror horizontally
        }
    }

    // Always start HTTP server so diagnostics and dashboard can connect
    startCameraServer();
}

// ========================================================
// 2. Audio Hardware Initialization (I2S Mic & Speaker)
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
    if (err == ESP_OK) {
        i2s_set_pin(I2S_NUM_0, &mic_pins);
        Serial.println("[I2S MIC] INMP441 initialized (SCK:41, WS:42, SD:2)");
    }
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
    if (err == ESP_OK) {
        i2s_set_pin(I2S_NUM_1, &spk_pins);
        Serial.println("[I2S SPK] MAX98357A initialized (BCLK:1, LRC:14, DIN:21)");
    }
}

void playAudioChunk(uint8_t *payload, size_t length) {
    if (length == 0 || !isSpeaking) return;

    size_t samples = length / 2;
    int16_t *mono_samples = (int16_t*)payload;
    static int16_t stereo_buf[512 * 2];
    size_t chunk_samples = 512;

    for (size_t i = 0; i < samples; i += chunk_samples) {
        if (!isSpeaking) break;
        size_t count = min(chunk_samples, samples - i);
        for (size_t j = 0; j < count; j++) {
            int16_t s = mono_samples[i + j];
            stereo_buf[j * 2] = s;
            stereo_buf[j * 2 + 1] = s;
        }
        size_t bytes_written = 0;
        i2s_write(I2S_NUM_1, stereo_buf, count * 4, &bytes_written, portMAX_DELAY);
    }
}

// ========================================================
// 3. WebSocket Event Handler
// ========================================================
void webSocketEvent(WStype_t type, uint8_t * payload, size_t length) {
    switch(type) {
        case WStype_DISCONNECTED:
            isConnectedToServer = false;
            Serial.println("[WS] Disconnected from Brain Server");
            break;

        case WStype_CONNECTED:
            isConnectedToServer = true;
            Serial.printf("[WS] Connected to %s:%d\n", SERVER_HOST, SERVER_PORT);
            webSocket.sendTXT("{\"client\":\"esp32_s3_unified\",\"board\":\"N16R8\",\"camera\":\"OV3660\",\"voice\":\"active\"}");
            break;

        case WStype_TEXT: {
            StaticJsonDocument<256> doc;
            DeserializationError error = deserializeJson(doc, payload, length);
            if (!error) {
                const char* event = doc["event"];
                if (event && strcmp(event, "speaking_start") == 0) {
                    isSpeaking = true;
                } else if (event && strcmp(event, "speaking_end") == 0) {
                    isSpeaking = false;
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
// 4. Microphone Recording Task (Pinned to Core 0)
// ========================================================
void micStreamingTask(void *param) {
    int32_t raw_buffer[256];
    int16_t pcm16_buffer[256];
    size_t bytes_read = 0;

    while (true) {
        bool shouldRecord = isConnectedToServer && !isSpeaking;

        if (shouldRecord) {
            esp_err_t result = i2s_read(I2S_NUM_0, raw_buffer, sizeof(raw_buffer), &bytes_read, pdMS_TO_TICKS(50));
            if (result == ESP_OK && bytes_read > 0) {
                size_t samples = bytes_read / sizeof(int32_t);

                for (size_t i = 0; i < samples; i++) {
                    int32_t val = raw_buffer[i] >> 15;
                    if (val > 32767) val = 32767;
                    else if (val < -32768) val = -32768;
                    pcm16_buffer[i] = (int16_t)val;
                }

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
// 5. Setup & Loop
// ========================================================
void setup() {
    Serial.begin(115200);
    delay(1000);

    Serial.println("\n=============================================");
    Serial.println("  IVIA - ESP32-S3 UNIFIED VOICE + VISION     ");
    Serial.println("         Autonomous Voice & Vision Node      ");
    Serial.println("=============================================");

    wsMutex = xSemaphoreCreateMutex();

    Serial.println("\n[Diagnostic] Checking PSRAM status...");
    if (psramFound()) {
        Serial.printf("[Diagnostic] PSRAM: ENABLED (%d bytes free, OPI PSRAM)\n", ESP.getFreePsram());
    } else {
        Serial.println("[Diagnostic] PSRAM: NOT DETECTED / DISABLED!");
        Serial.println("[Diagnostic] In Arduino IDE: Tools -> PSRAM -> Select 'OPI PSRAM'");
    }

    // 1. Initialize Audio Peripherals
    initI2SMicrophone();
    initI2SSpeaker();

    // 2. Connect to Wi-Fi
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
        WiFi.setSleep(false); // Disable Wi-Fi modem sleep to prevent packet drops and latency spikes
        Serial.println("\n[Wi-Fi] Connected!");
        Serial.printf("[Wi-Fi] IP Address: http://%s/\n", WiFi.localIP().toString().c_str());
    }

    // 3. Initialize OV3660 Camera Server
    initOV3660Camera();

    // 4. Initialize WebSocket Voice Client to Brain Server
    webSocket.begin(SERVER_HOST, SERVER_PORT, WS_PATH);
    webSocket.onEvent(webSocketEvent);
    webSocket.setReconnectInterval(3000);

    // 5. Launch Microphone Streaming Task on Core 0
    xTaskCreatePinnedToCore(
        micStreamingTask,
        "MicTask",
        8192,
        NULL,
        1,
        NULL,
        0
    );

    Serial.println("[System] IVIA Unified Voice & Vision Node is Online!");
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
            WiFi.reconnect();
        }
    }
}
