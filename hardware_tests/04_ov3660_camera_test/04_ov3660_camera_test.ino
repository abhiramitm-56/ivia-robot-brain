/**
 * TEST 4: OV3660 Camera Live Stream Test (Robust & Anti-Crash Edition)
 * Board: ESP32-S3 (N16R8) with OV3660 Camera Sensor
 * 
 * In Arduino IDE Tools Menu:
 *   - Board: "ESP32S3 Dev Module"
 *   - PSRAM: "OPI PSRAM" (N16R8 has 8MB Octal PSRAM)
 *   - Flash Size: "16MB"
 *   - USB CDC On Boot: "Enabled" (or "Disabled" depending on your USB port)
 * 
 * Features:
 *   1. Full HTML Web Portal at http://<ESP32_IP>/ with live video & flip button
 *   2. /stream endpoint for raw MJPEG video stream
 *   3. /capture endpoint for single JPEG snapshots (used by IVIA AI Dashboard)
 *   4. /flip endpoint to flip image orientation 180 degrees
 *   5. /status endpoint for health monitoring
 *   6. Thread-safe camera mutex preventing DMA buffer corruption & crashes
 *   7. WiFi.setSleep(false) preventing packet loss, latency spikes & Wi-Fi drops
 *   8. Auto-reconnect watchdog in loop()
 */

#include "esp_camera.h"
#include <WiFi.h>
#include "esp_http_server.h"

// ==========================================
// Replace with your Wi-Fi Credentials
// IMPORTANT: Both your PC and ESP32 MUST connect to the same Wi-Fi!
// ==========================================
// Option 1: Mobile Hotspot (Connect your laptop to this hotspot too)
const char* ssid = "Abhirami";
const char* password = "123454321";

// Option 2: Router Wi-Fi (If your laptop is on NextGenPro_4G, enter password below)
// const char* ssid = "NextGenPro_4G";
// const char* password = "YOUR_WIFI_PASSWORD";

// ==========================================
// Camera Pin Definitions (ESP32-S3 Cam Modules)
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
bool is_flipped = true; // Default: flipped 180 for standard ribbon orientation
bool camera_initialized = false;
esp_err_t camera_init_err = ESP_OK;

// ==========================================
// 1. Root HTML Web Page Handler
// ==========================================
static const char INDEX_HTML[] PROGMEM = R"rawliteral(
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>IVIA — OV3660 Live Stream</title>
  <style>
    :root {
      --bg: #090d16;
      --card: #131b2e;
      --border: #1e293b;
      --neon: #00f59b;
      --cyan: #00e5ff;
      --text: #f1f5f9;
      --muted: #94a3b8;
    }
    * { box-sizing: border-box; margin: 0; padding: 0; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; }
    body {
      background: var(--bg);
      color: var(--text);
      display: flex;
      flex-direction: column;
      align-items: center;
      justify-content: center;
      min-height: 100vh;
      padding: 20px;
    }
    .card {
      background: var(--card);
      border: 1px solid var(--border);
      border-radius: 16px;
      padding: 24px;
      max-width: 680px;
      width: 100%;
      box-shadow: 0 20px 40px rgba(0,0,0,0.5), 0 0 30px rgba(0,245,155,0.1);
      text-align: center;
    }
    .header {
      display: flex;
      align-items: center;
      justify-content: space-between;
      margin-bottom: 16px;
      padding-bottom: 12px;
      border-bottom: 1px solid var(--border);
    }
    .title {
      font-size: 1.25rem;
      font-weight: 700;
      color: var(--neon);
      display: flex;
      align-items: center;
      gap: 8px;
    }
    .badge {
      display: inline-flex;
      align-items: center;
      gap: 6px;
      padding: 4px 10px;
      border-radius: 20px;
      font-size: 0.75rem;
      font-weight: 600;
      background: rgba(0,245,155,0.15);
      color: var(--neon);
      border: 1px solid rgba(0,245,155,0.3);
    }
    .badge-dot {
      width: 8px;
      height: 8px;
      border-radius: 50%;
      background: var(--neon);
      box-shadow: 0 0 8px var(--neon);
      animation: pulse 1.5s infinite;
    }
    @keyframes pulse { 0%, 100% { opacity: 1; } 50% { opacity: 0.4; } }
    .stream-container {
      position: relative;
      border-radius: 12px;
      overflow: hidden;
      border: 2px solid var(--border);
      background: #000;
      min-height: 360px;
      display: flex;
      align-items: center;
      justify-content: center;
    }
    .stream-img {
      width: 100%;
      height: auto;
      display: block;
      object-fit: contain;
    }
    .controls {
      display: flex;
      gap: 12px;
      justify-content: center;
      margin-top: 18px;
      flex-wrap: wrap;
    }
    .btn {
      background: #1e293b;
      color: var(--text);
      border: 1px solid #334155;
      padding: 10px 18px;
      border-radius: 8px;
      font-weight: 600;
      font-size: 0.85rem;
      cursor: pointer;
      display: inline-flex;
      align-items: center;
      gap: 8px;
      transition: all 0.2s ease;
      text-decoration: none;
    }
    .btn:hover {
      background: #334155;
      border-color: var(--cyan);
      color: var(--cyan);
    }
    .btn-neon {
      background: rgba(0,245,155,0.15);
      border-color: var(--neon);
      color: var(--neon);
    }
    .btn-neon:hover {
      background: var(--neon);
      color: #000;
      box-shadow: 0 0 15px rgba(0,245,155,0.4);
    }
    .footer {
      margin-top: 14px;
      font-size: 0.75rem;
      color: var(--muted);
      line-height: 1.5;
    }
  </style>
</head>
<body>
  <div class="card">
    <div class="header">
      <div class="title">
        <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M23 7l-7 5 7 5V7z"/><rect x="1" y="5" width="15" height="14" rx="2" ry="2"/></svg>
        IVIA &bull; OV3660 Cam
      </div>
      <div class="badge">
        <span class="badge-dot"></span> LIVE 640x480
      </div>
    </div>

    <div class="stream-container">
      <img src="/stream" class="stream-img" id="liveStream" alt="Camera Live Feed" onerror="handleStreamError()">
    </div>

    <div class="controls">
      <button class="btn btn-neon" onclick="toggleFlip()">
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M7 16V4M7 4L3 8M7 4L11 8M17 8V20M17 20L21 16M17 20L13 16"/></svg>
        Flip 180&deg;
      </button>
      <a class="btn" href="/capture" target="_blank">
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="3"/><path d="M3 7V5a2 2 0 0 1 2-2h2"/><path d="M17 3h2a2 2 0 0 1 2 2v2"/><path d="M21 17v2a2 2 0 0 1-2 2h-2"/><path d="M7 21H5a2 2 0 0 1-2-2v-2"/></svg>
        Snapshot (/capture)
      </a>
      <button class="btn" onclick="location.reload()">
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="23 4 23 10 17 10"/><path d="M20.49 15a9 9 0 1 1-2.12-9.36L23 10"/></svg>
        Refresh Stream
      </button>
    </div>

    <div class="footer">
      ESP32-S3 N16R8 &bull; OV3660 3MP Sensor &bull; Octal PSRAM Enabled<br>
      Ready for IVIA AI Dashboard integration at <code>http://localhost:8000</code>
    </div>
  </div>

  <script>
    function toggleFlip() {
      fetch('/flip')
        .then(r => r.json())
        .then(data => {
          console.log("Flipped:", data);
          const img = document.getElementById('liveStream');
          img.src = '/stream?t=' + Date.now();
        })
        .catch(e => console.error("Flip error:", e));
    }
    function handleStreamError() {
      setTimeout(() => {
        const img = document.getElementById('liveStream');
        img.src = '/stream?t=' + Date.now();
      }, 2000);
    }
  </script>
</body>
</html>
)rawliteral";

static esp_err_t index_handler(httpd_req_t *req) {
    httpd_resp_set_type(req, "text/html");
    httpd_resp_set_hdr(req, "Access-Control-Allow-Origin", "*");

    if (!camera_initialized) {
        char errPage[700];
        snprintf(errPage, sizeof(errPage),
            "<!DOCTYPE html><html><body style='font-family:sans-serif;background:#090d16;color:#f1f5f9;text-align:center;padding:40px;'>"
            "<h1 style='color:#ef4444;'>OV3660 Camera Sensor Failed (0x%x)</h1>"
            "<p style='color:#f59e0b;font-size:1.1rem;'><b>%s</b></p>"
            "<div style='max-width:550px;margin:20px auto;text-align:left;background:#131b2e;padding:20px;border-radius:12px;border:1px solid #1e293b;line-height:1.6;'>"
            "<b>Troubleshooting Checklist:</b><br>"
            "1. <b>FPC Ribbon Cable:</b> Lift the black latch on the FPC connector, gently push the ribbon all the way in with gold contacts facing the PCB, and snap the latch closed.<br>"
            "2. <b>PSRAM:</b> In Arduino IDE Tools menu, verify <b>PSRAM: OPI PSRAM</b> is selected.<br>"
            "3. <b>Reset:</b> Press the physical RST button on the ESP32-S3."
            "</div><p><a href='/status' style='color:#00e5ff;'>View Diagnostic JSON (/status)</a></p>"
            "</body></html>",
            camera_init_err,
            (camera_init_err == 0x105) ? "Error 0x105: ESP_ERR_NOT_FOUND (Sensor I2C not responding - check ribbon cable!)" :
            (camera_init_err == 0x101) ? "Error 0x101: ESP_ERR_NO_MEM (Out of RAM - set Tools > PSRAM to OPI PSRAM!)" : "Camera hardware initialization error"
        );
        return httpd_resp_send(req, errPage, HTTPD_RESP_USE_STRLEN);
    }

    return httpd_resp_send(req, INDEX_HTML, HTTPD_RESP_USE_STRLEN);
}

// ==========================================
// 2. Single Frame Snapshot Handler (/capture)
// ==========================================
static esp_err_t capture_handler(httpd_req_t *req) {
    if (!camera_initialized) {
        httpd_resp_set_status(req, "503 Service Unavailable");
        httpd_resp_set_type(req, "application/json");
        httpd_resp_set_hdr(req, "Access-Control-Allow-Origin", "*");
        char buf[128];
        snprintf(buf, sizeof(buf), "{\"error\":\"Camera sensor not initialized\",\"code\":\"0x%x\"}", camera_init_err);
        return httpd_resp_send(req, buf, HTTPD_RESP_USE_STRLEN);
    }

    if (camera_mutex && xSemaphoreTake(camera_mutex, pdMS_TO_TICKS(1500)) != pdTRUE) {
        Serial.println("[Camera] Mutex timeout during capture");
        httpd_resp_send_500(req);
        return ESP_FAIL;
    }

    camera_fb_t * fb = esp_camera_fb_get();
    if (!fb || fb->len == 0) {
        if (fb) esp_camera_fb_return(fb);
        if (camera_mutex) xSemaphoreGive(camera_mutex);
        Serial.println("[Camera] Frame capture failed: NULL or empty buffer");
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

// ==========================================
// 3. MJPEG Live Video Stream Handler (/stream)
// ==========================================
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
                vTaskDelay(pdMS_TO_TICKS(10));
                continue;
            }

            size_t hlen = snprintf(part_buf, 64, _STREAM_PART, fb->len);
            res = httpd_resp_send_chunk(req, _STREAM_BOUNDARY, strlen(_STREAM_BOUNDARY));
            if (res == ESP_OK) res = httpd_resp_send_chunk(req, part_buf, hlen);
            if (res == ESP_OK) res = httpd_resp_send_chunk(req, (const char *)fb->buf, fb->len);
            esp_camera_fb_return(fb);
            xSemaphoreGive(camera_mutex);
        } else {
            vTaskDelay(pdMS_TO_TICKS(20));
            continue;
        }

        if (res != ESP_OK) break;
        vTaskDelay(pdMS_TO_TICKS(35)); // ~25 FPS smooth streaming
    }
    return res;
}

// ==========================================
// 4. Flip Orientation Toggle Handler (/flip)
// ==========================================
static esp_err_t flip_handler(httpd_req_t *req) {
    sensor_t * s = esp_camera_sensor_get();
    if (s != NULL) {
        is_flipped = !is_flipped;
        s->set_vflip(s, is_flipped ? 1 : 0);
        s->set_hmirror(s, is_flipped ? 1 : 0);
        char resp[64];
        snprintf(resp, sizeof(resp), "{\"success\":true,\"flipped\":%s}", is_flipped ? "true" : "false");
        httpd_resp_set_type(req, "application/json");
        httpd_resp_set_hdr(req, "Access-Control-Allow-Origin", "*");
        return httpd_resp_send(req, resp, HTTPD_RESP_USE_STRLEN);
    }
    httpd_resp_send_500(req);
    return ESP_FAIL;
}

// ==========================================
// 5. System Status Handler (/status)
// ==========================================
static esp_err_t status_handler(httpd_req_t *req) {
    char resp[128];
    snprintf(resp, sizeof(resp), "{\"status\":\"ok\",\"ip\":\"%s\",\"free_psram\":%d,\"free_heap\":%d}",
             WiFi.localIP().toString().c_str(), ESP.getFreePsram(), ESP.getFreeHeap());
    httpd_resp_set_type(req, "application/json");
    httpd_resp_set_hdr(req, "Access-Control-Allow-Origin", "*");
    return httpd_resp_send(req, resp, HTTPD_RESP_USE_STRLEN);
}

// ==========================================
// 6. Camera Server Starter
// ==========================================
void startCameraServer() {
    httpd_config_t config = HTTPD_DEFAULT_CONFIG();
    config.server_port = 80;
    config.ctrl_port = 32768;
    config.max_open_sockets = 7;
    config.lru_purge_enable = true; // Automatically purges old/idle sockets to prevent exhaustion
    config.stack_size = 8192;       // Prevent stack overflow in HTTP worker task

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

    httpd_uri_t flip_uri = {
        .uri       = "/flip",
        .method    = HTTP_GET,
        .handler   = flip_handler,
        .user_ctx  = NULL
    };

    httpd_uri_t status_uri = {
        .uri       = "/status",
        .method    = HTTP_GET,
        .handler   = status_handler,
        .user_ctx  = NULL
    };

    if (httpd_start(&camera_httpd, &config) == ESP_OK) {
        httpd_register_uri_handler(camera_httpd, &index_uri);
        httpd_register_uri_handler(camera_httpd, &stream_uri);
        httpd_register_uri_handler(camera_httpd, &capture_uri);
        httpd_register_uri_handler(camera_httpd, &flip_uri);
        httpd_register_uri_handler(camera_httpd, &status_uri);
        Serial.println("[Camera] Web Server started successfully!");
    } else {
        Serial.println("[Camera] Failed to start HTTP server!");
    }
}

// ==========================================
// 7. Arduino Setup & Loop
// ==========================================
void setup() {
    Serial.begin(115200);
    delay(1000);
    Serial.println("\n=============================================");
    Serial.println("  IVIA - OV3660 CAMERA SERVER (ROBUST)       ");
    Serial.println("=============================================");

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
    config.xclk_freq_hz = 10000000;         // 10MHz prevents DMA buffer overflow (FB-OVF) on ESP32-S3
    config.pixel_format = PIXFORMAT_JPEG;
    config.grab_mode = CAMERA_GRAB_WHEN_EMPTY; // Only fill buffer when requested (stops FB-OVF spam)
    config.jpeg_quality = 14;

    // Check PSRAM & configure buffers accordingly
    if (psramFound()) {
        Serial.printf("[System] PSRAM Detected: %d bytes free. Dual 640x480 PSRAM buffers.\n", ESP.getFreePsram());
        config.frame_size = FRAMESIZE_VGA;      // 640x480
        config.fb_location = CAMERA_FB_IN_PSRAM;
        config.fb_count = 2;
    } else {
        Serial.println("[System] WARNING: PSRAM NOT detected! Falling back to DRAM 320x240.");
        Serial.println("[System] TIP: In Arduino IDE Tools menu, set PSRAM: 'OPI PSRAM'");
        config.frame_size = FRAMESIZE_QVGA;     // 320x240 fallback
        config.fb_location = CAMERA_FB_IN_DRAM;
        config.fb_count = 1;
        config.jpeg_quality = 16;
    }

    // Initialize Camera Sensor
    esp_err_t err = esp_camera_init(&config);
    if (err != ESP_OK) {
        Serial.printf("[Camera] Init failed with error 0x%x\n", err);
        return;
    }
    Serial.println("[Camera] OV3660 initialized successfully!");

    // Set initial orientation (vflip=1, hmirror=1 right-side up)
    sensor_t * s = esp_camera_sensor_get();
    if (s != NULL) {
        s->set_vflip(s, is_flipped ? 1 : 0);
        s->set_hmirror(s, is_flipped ? 1 : 0);
    }

    // Connect to Wi-Fi
    Serial.printf("[Wi-Fi] Connecting to '%s'", ssid);
    WiFi.mode(WIFI_STA);
    WiFi.begin(ssid, password);
    int attempts = 0;
    while (WiFi.status() != WL_CONNECTED && attempts < 40) {
        delay(500);
        Serial.print(".");
        attempts++;
    }

    if (WiFi.status() == WL_CONNECTED) {
        // Disable Wi-Fi modem sleep to prevent packet drops and latency spikes!
        WiFi.setSleep(false);

        Serial.println("\n[Wi-Fi] Connected successfully!");
        Serial.print("[Camera] Web Stream Portal: http://");
        Serial.println(WiFi.localIP());
        Serial.print("[Camera] Direct Snapshot URL: http://");
        Serial.print(WiFi.localIP());
        Serial.println("/capture");

        startCameraServer();
    } else {
        Serial.println("\n[Wi-Fi] Failed to connect! Verify SSID and Password.");
    }
}

void loop() {
    // Wi-Fi Connection Watchdog & Auto-Reconnect
    if (WiFi.status() != WL_CONNECTED) {
        static unsigned long lastReconnect = 0;
        if (millis() - lastReconnect > 5000) {
            lastReconnect = millis();
            Serial.println("[Wi-Fi] Connection lost! Reconnecting...");
            WiFi.reconnect();
        }
    }
    delay(100);
}
