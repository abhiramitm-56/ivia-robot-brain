/**
 * TEST 5: Standalone OV3660 Vision Node (Object & Gesture Streaming)
 * Board: ESP32-S3 (N16R8) with OV3660 Camera Sensor
 * 
 * Works directly with vision_dashboard.py on your PC
 * 
 * In Arduino IDE Tools Menu:
 *   - Board: "ESP32S3 Dev Module"
 *   - PSRAM: "OPI PSRAM" (N16R8 has 8MB Octal PSRAM)
 *   - Flash Size: "16MB"
 *   - USB CDC On Boot: "Enabled"
 */

#include "esp_camera.h"
#include <WiFi.h>
#include "esp_http_server.h"

// ==========================================
// 1. Wi-Fi Credentials
// ==========================================
const char* ssid = "Abhirami";          // Replace if using another Wi-Fi
const char* password = "123454321";     // Replace if using another Wi-Fi

// ==========================================
// 2. Camera Pin Definitions (ESP32-S3 OV3660)
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

httpd_handle_t camera_httpd = NULL;
SemaphoreHandle_t camera_mutex = NULL;
bool is_flipped = true;
bool camera_initialized = false;
esp_err_t camera_init_err = ESP_OK;

// ==========================================
// 3. Web Page Handlers
// ==========================================
static const char INDEX_HTML[] PROGMEM = R"rawliteral(
<!DOCTYPE html>
<html>
<head>
  <meta charset="UTF-8">
  <title>ESP32-S3 OV3660 Vision Node</title>
  <style>
    body { background: #0b0f19; color: #f1f5f9; font-family: sans-serif; text-align: center; padding: 20px; }
    .card { background: #131b2e; border: 1px solid #1e293b; border-radius: 12px; display: inline-block; padding: 20px; max-width: 680px; }
    img { width: 100%; border-radius: 8px; border: 1px solid #334155; }
    .status { color: #00f59b; font-weight: bold; margin: 10px 0; }
  </style>
</head>
<body>
  <div class="card">
    <h2>ESP32-S3 OV3660 Vision Node</h2>
    <p class="status">&bull; Camera Ready for AI Dashboard</p>
    <img src="/stream" alt="Live Feed">
    <p style="color:#94a3b8; font-size:14px; margin-top:12px;">Run <code>python vision_dashboard.py</code> on your PC to start Object & Gesture Detection.</p>
  </div>
</body>
</html>
)rawliteral";

static esp_err_t index_handler(httpd_req_t *req) {
    httpd_resp_set_type(req, "text/html");
    httpd_resp_set_hdr(req, "Access-Control-Allow-Origin", "*");
    return httpd_resp_send(req, INDEX_HTML, HTTPD_RESP_USE_STRLEN);
}

static esp_err_t capture_handler(httpd_req_t *req) {
    if (!camera_initialized) {
        httpd_resp_send_500(req);
        return ESP_FAIL;
    }

    if (camera_mutex && xSemaphoreTake(camera_mutex, pdMS_TO_TICKS(1500)) != pdTRUE) {
        httpd_resp_send_500(req);
        return ESP_FAIL;
    }

    camera_fb_t * fb = esp_camera_fb_get();
    if (!fb || fb->len == 0) {
        if (fb) esp_camera_fb_return(fb);
        if (camera_mutex) xSemaphoreGive(camera_mutex);
        httpd_resp_send_500(req);
        return ESP_FAIL;
    }

    httpd_resp_set_type(req, "image/jpeg");
    httpd_resp_set_hdr(req, "Content-Disposition", "inline; filename=capture.jpg");
    httpd_resp_set_hdr(req, "Access-Control-Allow-Origin", "*");
    httpd_resp_set_hdr(req, "Cache-Control", "no-cache, no-store, must-revalidate");

    esp_err_t res = httpd_resp_send(req, (const char *)fb->buf, fb->len);
    esp_camera_fb_return(fb);

    if (camera_mutex) xSemaphoreGive(camera_mutex);
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
        if (camera_mutex && xSemaphoreTake(camera_mutex, pdMS_TO_TICKS(500)) == pdTRUE) {
            fb = esp_camera_fb_get();
            if (!fb) {
                xSemaphoreGive(camera_mutex);
                delay(10);
                continue;
            }

            size_t hlen = snprintf(part_buf, 64, _STREAM_PART, fb->len);
            res = httpd_resp_send_chunk(req, _STREAM_BOUNDARY, strlen(_STREAM_BOUNDARY));
            if (res == ESP_OK) res = httpd_resp_send_chunk(req, part_buf, hlen);
            if (res == ESP_OK) res = httpd_resp_send_chunk(req, (const char *)fb->buf, fb->len);
            
            esp_camera_fb_return(fb);
            xSemaphoreGive(camera_mutex);
        } else {
            delay(10);
            continue;
        }

        if (res != ESP_OK) break;
        delay(1);
    }
    return res;
}

void startCameraServer() {
    httpd_config_t config = HTTPD_DEFAULT_CONFIG();
    config.server_port = 80;
    config.ctrl_port = 32768;
    config.max_uri_handlers = 8;

    httpd_uri_t index_uri = { .uri = "/", .method = HTTP_GET, .handler = index_handler, .user_ctx = NULL };
    httpd_uri_t stream_uri = { .uri = "/stream", .method = HTTP_GET, .handler = stream_handler, .user_ctx = NULL };
    httpd_uri_t capture_uri = { .uri = "/capture", .method = HTTP_GET, .handler = capture_handler, .user_ctx = NULL };

    if (httpd_start(&camera_httpd, &config) == ESP_OK) {
        httpd_register_uri_handler(camera_httpd, &index_uri);
        httpd_register_uri_handler(camera_httpd, &stream_uri);
        httpd_register_uri_handler(camera_httpd, &capture_uri);
        Serial.println("[Camera] HTTP Server running on port 80!");
    } else {
        Serial.println("[Camera] Error starting server!");
    }
}

void setup() {
    Serial.begin(115200);
    delay(1000);
    Serial.println("\n--- Starting Standalone OV3660 Vision Node ---");

    camera_mutex = xSemaphoreCreateMutex();

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
    config.xclk_freq_hz = 10000000;         // 10MHz prevents DMA overflow
    config.pixel_format = PIXFORMAT_JPEG;
    config.grab_mode = CAMERA_GRAB_WHEN_EMPTY;
    config.jpeg_quality = 14;

    if (psramFound()) {
        Serial.printf("[System] PSRAM Detected (%d bytes free). Dual 640x480 buffers.\n", ESP.getFreePsram());
        config.frame_size = FRAMESIZE_VGA;      // 640x480
        config.fb_location = CAMERA_FB_IN_PSRAM;
        config.fb_count = 2;
    } else {
        Serial.println("[System] WARNING: PSRAM not enabled! Falling back to 320x240.");
        config.frame_size = FRAMESIZE_QVGA;
        config.fb_location = CAMERA_FB_IN_DRAM;
        config.fb_count = 1;
        config.jpeg_quality = 16;
    }

    camera_init_err = esp_camera_init(&config);
    if (camera_init_err != ESP_OK) {
        Serial.printf("[Camera] Init failed (0x%x)\n", camera_init_err);
        return;
    }
    camera_initialized = true;
    Serial.println("[Camera] OV3660 Initialized!");

    sensor_t * s = esp_camera_sensor_get();
    if (s != NULL) {
        s->set_vflip(s, is_flipped ? 1 : 0);
        s->set_hmirror(s, is_flipped ? 1 : 0);
    }

    WiFi.mode(WIFI_STA);
    WiFi.begin(ssid, password);
    Serial.printf("[Wi-Fi] Connecting to '%s'", ssid);
    int attempts = 0;
    while (WiFi.status() != WL_CONNECTED && attempts < 40) {
        delay(500);
        Serial.print(".");
        attempts++;
    }

    if (WiFi.status() == WL_CONNECTED) {
        WiFi.setSleep(false); // Prevents Wi-Fi latency & packet drops
        Serial.println("\n[Wi-Fi] Connected!");
        Serial.print(">>> Camera IP: http://");
        Serial.println(WiFi.localIP());
        Serial.println(">>> Use this IP in vision_dashboard.py");
        startCameraServer();
    } else {
        Serial.println("\n[Wi-Fi] Failed to connect. Check SSID and password.");
    }
}

void loop() {
    if (WiFi.status() != WL_CONNECTED) {
        static unsigned long lastReconnect = 0;
        if (millis() - lastReconnect > 5000) {
            lastReconnect = millis();
            WiFi.reconnect();
        }
    }
    delay(100);
}

