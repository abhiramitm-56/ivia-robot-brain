/**
 * IVIA Portal Web Controller
 * Handles WebSocket connection, live audio visualizer, chat UI, and audio playback.
 */

// Web Elements
const esp32Dot = document.getElementById("esp32Dot");
const esp32Label = document.getElementById("esp32Label");
const serverDot = document.getElementById("serverDot");
const serverLabel = document.getElementById("serverLabel");
const robotStateBadge = document.getElementById("robotStateBadge");
const avatarRing = document.getElementById("avatarRing");
const chatHistory = document.getElementById("chatHistory");
const manualInput = document.getElementById("manualInput");
const waveformCanvas = document.getElementById("waveformCanvas");
const canvasCtx = waveformCanvas.getContext("2d");

// Tabs & Panels
const tabQA = document.getElementById("tabQA");
const tabVision = document.getElementById("tabVision");
const panelQA = document.getElementById("panelQA");
const panelVision = document.getElementById("panelVision");

// State
let ws = null;
let currentRMS = 0;
let smoothedRMS = 0;
let audioContext = null;
let activeMode = "general_qa";

// ==========================================
// WebSocket Connection
// ==========================================
function connectWebSocket() {
    const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
    const wsUrl = `${protocol}//${window.location.host}/ws/web`;

    ws = new WebSocket(wsUrl);
    ws.binaryType = "arraybuffer";

    ws.onopen = () => {
        serverDot.className = "status-dot connected";
        serverLabel.textContent = "Brain Online";
        fetch("/api/status")
            .then(r => r.json())
            .then(d => {
                if (d.esp32_connected) {
                    updateESP32Status(true, d.esp32_ip);
                }
            })
            .catch(() => {});
    };

    ws.onclose = () => {
        serverDot.className = "status-dot disconnected";
        serverLabel.textContent = "Reconnecting...";
        setTimeout(connectWebSocket, 3000);
    };

    ws.onerror = (err) => {
        console.error("[WS] Error:", err);
    };

    ws.onmessage = async (event) => {
        // Handle binary audio from server (plays on web browser speaker too!)
        if (event.data instanceof ArrayBuffer) {
            playRawPCM(event.data);
            return;
        }

        try {
            const data = JSON.parse(event.data);
            handleServerEvent(data);
        } catch (e) {
            console.error("[WS] Parse error:", e);
        }
    };
}

function handleServerEvent(data) {
    switch (data.event) {
        case "init":
            updateESP32Status(data.esp32_connected, data.esp32_ip);
            updateRobotState(data.state);
            switchMode(data.mode, false);
            break;

        case "esp32_status":
            updateESP32Status(data.connected, data.ip);
            break;

        case "state_change":
            updateRobotState(data.state);
            break;

        case "audio_level":
            currentRMS = data.rms || 0;
            break;

        case "transcript":
            appendChatMessage(data.role, data.text);
            break;

        case "mode_changed":
            switchMode(data.mode, false);
            break;

        case "vision_result":
            if (data.data) {
                handleVisionResult(data.data);
            }
            break;
    }
}

// ==========================================
// UI Updates
// ==========================================
function updateESP32Status(connected, ip) {
    if (connected) {
        esp32Dot.className = "status-dot connected";
        esp32Label.textContent = ip ? `ESP32 Node Active (${ip})` : "ESP32 Voice Node Active";
        if (esp32CamIp && ip && !esp32CamIp.value) {
            esp32CamIp.value = ip;
        }
    } else {
        esp32Dot.className = "status-dot disconnected";
        esp32Label.textContent = "ESP32 Offline (Waiting)";
    }
}

function updateRobotState(state) {
    robotStateBadge.className = `state-badge ${state}`;
    avatarRing.className = `avatar-ring ${state}`;

    if (state === "idle") {
        robotStateBadge.textContent = "STANDBY / IDLE";
    } else if (state === "listening") {
        robotStateBadge.textContent = "LISTENING (MIC ACTIVE)...";
    } else if (state === "processing") {
        robotStateBadge.textContent = "THINKING (AI REASONING)...";
    } else if (state === "speaking") {
        robotStateBadge.textContent = "SPEAKING (I2S AUDIO OUT)...";
    }
}

function appendChatMessage(role, text) {
    const bubble = document.createElement("div");
    bubble.className = `chat-bubble ${role}`;

    const isIvia = role === "ivia";
    const header = document.createElement("div");
    header.className = "bubble-header";

    const nameSpan = document.createElement("span");
    nameSpan.className = "speaker-name";
    nameSpan.textContent = isIvia ? "IVIA (HUMANOID COMPANION)" : "USER (INMP441 / WEB)";

    const timeSpan = document.createElement("span");
    timeSpan.className = "bubble-time";
    timeSpan.textContent = new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' });

    header.appendChild(nameSpan);
    header.appendChild(timeSpan);

    const textDiv = document.createElement("div");
    textDiv.className = "bubble-text";
    textDiv.textContent = text;

    bubble.appendChild(header);
    bubble.appendChild(textDiv);

    chatHistory.appendChild(bubble);
    chatHistory.scrollTop = chatHistory.scrollHeight;
}

// ==========================================
// Mode Switching
// ==========================================
function switchMode(mode, notifyServer = true) {
    if (activeMode === mode && !notifyServer) return;
    activeMode = mode;
    if (mode === "general_qa") {
        tabQA.classList.add("active");
        tabVision.classList.remove("active");
        panelQA.classList.add("active");
        panelVision.classList.remove("active");
    } else {
        tabVision.classList.add("active");
        tabQA.classList.remove("active");
        panelVision.classList.add("active");
        panelQA.classList.remove("active");
    }

    if (notifyServer && ws && ws.readyState === WebSocket.OPEN) {
        ws.send(JSON.stringify({ action: "set_mode", mode: mode }));
    }
}

// ==========================================
// Interactions & Chat
// ==========================================
function sendPrompt(text) {
    if (!text || !ws || ws.readyState !== WebSocket.OPEN) return;
    ws.send(JSON.stringify({ action: "chat", text: text }));
}

function sendManualInput() {
    const text = manualInput.value.trim();
    if (text) {
        sendPrompt(text);
        manualInput.value = "";
    }
}

function handleInputKey(e) {
    if (e.key === "Enter") {
        sendManualInput();
    }
}

// ==========================================
// Web Audio Context (Browser Playback)
// ==========================================
function playRawPCM(arrayBuffer) {
    try {
        if (!audioContext) {
            audioContext = new (window.AudioContext || window.webkitAudioContext)({ sampleRate: 16000 });
        }
        if (audioContext.state === "suspended") {
            audioContext.resume();
        }

        const int16Array = new Int16Array(arrayBuffer);
        const floatArray = new Float32Array(int16Array.length);
        for (let i = 0; i < int16Array.length; i++) {
            floatArray[i] = int16Array[i] / 32768.0;
        }

        const audioBuffer = audioContext.createBuffer(1, floatArray.length, 16000);
        audioBuffer.copyToChannel(floatArray, 0);

        const source = audioContext.createBufferSource();
        source.buffer = audioBuffer;
        source.connect(audioContext.destination);
        source.start();
    } catch (e) {
        console.error("[WebAudio] Playback failed:", e);
    }
}

// ==========================================
// Smooth Waveform Visualizer
// ==========================================
let phase = 0;
function renderVisualizer() {
    requestAnimationFrame(renderVisualizer);

    // Smooth decay
    smoothedRMS += (currentRMS - smoothedRMS) * 0.15;
    currentRMS *= 0.85; // Natural decay

    const w = waveformCanvas.width;
    const h = waveformCanvas.height;
    canvasCtx.clearRect(0, 0, w, h);

    const centerY = h / 2;
    const amplitude = Math.min(30, (smoothedRMS / 800) * 20);

    phase += 0.08;

    // Draw Glowing Oscilloscope Wave
    canvasCtx.beginPath();
    canvasCtx.lineWidth = 2;
    canvasCtx.strokeStyle = smoothedRMS > 300 ? "#00f59b" : "#00f2fe";
    canvasCtx.shadowColor = smoothedRMS > 300 ? "rgba(0, 245, 155, 0.8)" : "rgba(0, 242, 254, 0.6)";
    canvasCtx.shadowBlur = 8;

    for (let x = 0; x < w; x++) {
        const angle = (x / w) * Math.PI * 4 + phase;
        const y = centerY + Math.sin(angle) * (amplitude + 2);
        if (x === 0) {
            canvasCtx.moveTo(x, y);
        } else {
            canvasCtx.lineTo(x, y);
        }
    }
    canvasCtx.stroke();
    canvasCtx.shadowBlur = 0;
}

// Start visualizer loop and WS connection
renderVisualizer();
connectWebSocket();

// ========================================================
// SECTION 2: OBJECT & HAND GESTURE DETECTION CONTROLLER
// ========================================================

// Vision Elements
const srcWebcam = document.getElementById("srcWebcam");
const srcESP32 = document.getElementById("srcESP32");
const esp32IpBox = document.getElementById("esp32IpBox");
const esp32CamIp = document.getElementById("esp32CamIp");

const filterPersons = document.getElementById("filterPersons");
const filterObjects = document.getElementById("filterObjects");
const filterGestures = document.getElementById("filterGestures");
const chkPersons = document.getElementById("chkPersons");
const chkObjects = document.getElementById("chkObjects");
const chkGestures = document.getElementById("chkGestures");

const btnToggleVision = document.getElementById("btnToggleVision");
const streamIcon = document.getElementById("streamIcon");
const streamBtnText = document.getElementById("streamBtnText");

const feedPlaceholder = document.getElementById("feedPlaceholder");
const webcamVideo = document.getElementById("webcamVideo");
const visionCanvas = document.getElementById("visionCanvas");
const visionCtx = visionCanvas.getContext("2d");
const cameraStreamImg = document.getElementById("cameraStreamImg");

const hudTelemetry = document.getElementById("hudTelemetry");
const hudLiveDot = document.getElementById("hudLiveDot");
const hudStatus = document.getElementById("hudStatus");
const hudFps = document.getElementById("hudFps");
const hudRes = document.getElementById("hudRes");

const hudGestureBanner = document.getElementById("hudGestureBanner");
const hudGestureIcon = document.getElementById("hudGestureIcon");
const hudGestureName = document.getElementById("hudGestureName");
const hudGestureConf = document.getElementById("hudGestureConf");

const badgeTotalTargets = document.getElementById("badgeTotalTargets");
const kpiPersons = document.getElementById("kpiPersons");
const kpiObjects = document.getElementById("kpiObjects");
const kpiGestures = document.getElementById("kpiGestures");

const detectionList = document.getElementById("detectionList");
const detectionEmpty = document.getElementById("detectionEmpty");

// Vision State
let isVisionStreaming = false;
let currentVisionSource = "webcam";
let mediaStream = null;
let visionFrameTimer = null;
let isProcessingFrame = false;
let frameCounter = 0;
let lastFpsCheck = performance.now();
let hiddenOffscreenCanvas = document.createElement("canvas");
let hiddenCtx = hiddenOffscreenCanvas.getContext("2d");
let lastAnnouncedGesture = null;
let gestureClearTimer = null;
let isCameraFlipped = false;
let lastCardsHtml = "";
const reusableAnnotatedImg = new Image();

const cameraViewport = document.getElementById("cameraViewport");
const btnFlipCam = document.getElementById("btnFlipCam");

function toggleCameraFlip() {
    isCameraFlipped = !isCameraFlipped;
    if (btnFlipCam) btnFlipCam.classList.toggle("active", isCameraFlipped);
    if (cameraViewport) cameraViewport.classList.toggle("flipped", isCameraFlipped);
    console.log("[Vision] Camera flipped:", isCameraFlipped);
}

// Object Icons Map
const OBJECT_ICONS = {
    "person": "👤",
    "cell phone": "📱",
    "cup": "☕",
    "bottle": "🧴",
    "laptop": "💻",
    "mouse": "🖱️",
    "keyboard": "⌨️",
    "remote": "🎛️",
    "book": "📖",
    "clock": "⏰",
    "scissors": "✂️",
    "backpack": "🎒",
    "handbag": "👜",
    "wine glass": "🍷",
    "bowl": "🥣",
    "apple": "🍎",
    "banana": "🍌",
    "orange": "🍊",
    "sandwich": "🥪",
    "pizza": "🍕",
    "cake": "🎂",
    "chair": "🪑",
    "teddy bear": "🧸",
    "toothbrush": "🪥"
};

const GESTURE_ICONS = {
    "Open_Palm": "🖐️",
    "Closed_Fist": "✊",
    "Pointing_Up": "☝️",
    "Thumb_Up": "👍",
    "Thumb_Down": "👎",
    "Victory": "✌️",
    "ILoveYou": "🤟",
    "OK_Sign": "👌",
    "Pinch": "🤏",
    "Rock_On": "🤘"
};

function setVisionSource(source) {
    if (currentVisionSource === source) return;
    currentVisionSource = source;

    if (source === "webcam") {
        srcWebcam.classList.add("active");
        srcESP32.classList.remove("active");
        esp32IpBox.classList.add("hidden");
    } else {
        srcESP32.classList.add("active");
        srcWebcam.classList.remove("active");
        esp32IpBox.classList.remove("hidden");
        if (esp32CamIp && !esp32CamIp.value) {
            fetch("/api/status")
                .then(r => r.json())
                .then(d => {
                    if (d.esp32_ip && !esp32CamIp.value) {
                        esp32CamIp.value = d.esp32_ip;
                    }
                })
                .catch(() => {});
        }
    }

    if (isVisionStreaming) {
        stopVisionStream();
        toggleVisionStream();
    }
}

function toggleFilter(category) {
    if (category === "persons") {
        filterPersons.classList.toggle("active", chkPersons.checked);
    } else if (category === "objects") {
        filterObjects.classList.toggle("active", chkObjects.checked);
    } else if (category === "gestures") {
        filterGestures.classList.toggle("active", chkGestures.checked);
    }
}

async function toggleVisionStream() {
    if (isVisionStreaming) {
        stopVisionStream();
    } else {
        await startVisionStream();
    }
}

async function startVisionStream() {
    isVisionStreaming = true;
    btnToggleVision.classList.add("streaming");
    streamBtnText.textContent = "Stop Camera Feed";
    streamIcon.innerHTML = '<rect x="6" y="6" width="12" height="12"/>';
    hudStatus.textContent = "LIVE TRACKING";
    hudLiveDot.style.background = "#00f59b";

    feedPlaceholder.classList.add("hidden");
    feedPlaceholder.style.display = "none";
    visionCanvas.classList.remove("hidden");
    visionCanvas.style.display = "block";

    if (currentVisionSource === "webcam") {
        try {
            mediaStream = await navigator.mediaDevices.getUserMedia({
                video: { width: { ideal: 640 }, height: { ideal: 480 } }
            });
            webcamVideo.srcObject = mediaStream;
            await webcamVideo.play();

            visionCanvas.width = 640;
            visionCanvas.height = 480;
            hiddenOffscreenCanvas.width = 640;
            hiddenOffscreenCanvas.height = 480;
            hudRes.textContent = `${webcamVideo.videoWidth || 640}x${webcamVideo.videoHeight || 480}`;

            // Process vision frames every 120ms (~8 FPS for smooth CPU inference)
            visionFrameTimer = setInterval(captureAndSendWebcamFrame, 120);
        } catch (err) {
            console.error("[Vision] Webcam access error:", err);
            alert("Could not access camera: " + err.message);
            stopVisionStream();
            return;
        }
    } else {
        // ESP32 OV3660 Camera Stream (Flicker-Free AI Pipeline)
        let espIp = (esp32CamIp.value || "").trim();
        if (!espIp) {
            try {
                const s = await fetch("/api/status").then(r => r.json());
                if (s.esp32_ip) {
                    espIp = s.esp32_ip;
                    esp32CamIp.value = espIp;
                }
            } catch (e) {}
        }
        if (!espIp) {
            alert("Please enter your ESP32 IP address (e.g., 10.35.199.118)");
            stopVisionStream();
            return;
        }

        // Use visionCanvas directly to eliminate element toggling & flashing
        visionCanvas.width = 640;
        visionCanvas.height = 480;
        visionCanvas.classList.remove("hidden");
        cameraStreamImg.classList.add("hidden");

        hudStatus.textContent = "CONNECTING...";
        hudLiveDot.style.background = "#00f59b";

        // Start chained adaptive frame fetching (zero collisions, zero dropouts)
        scheduleNextESP32Frame();
    }

    // Start FPS counter
    lastFpsCheck = performance.now();
    frameCounter = 0;
}

function stopVisionStream() {
    isVisionStreaming = false;
    btnToggleVision.classList.remove("streaming");
    streamBtnText.textContent = "Start Camera Feed";
    streamIcon.innerHTML = '<polygon points="5 3 19 12 5 21 5 3"/>';
    hudStatus.textContent = "STANDBY";
    hudLiveDot.style.background = "#64748b";
    hudFps.textContent = "--";

    if (visionFrameTimer) {
        clearTimeout(visionFrameTimer);
        clearInterval(visionFrameTimer);
        visionFrameTimer = null;
    }

    if (mediaStream) {
        mediaStream.getTracks().forEach(track => track.stop());
        mediaStream = null;
    }
    webcamVideo.srcObject = null;
    cameraStreamImg.src = "";
    cameraStreamImg.classList.add("hidden");

    feedPlaceholder.classList.remove("hidden");
    feedPlaceholder.style.display = "block";
    visionCanvas.classList.add("hidden");
    visionCanvas.style.display = "none";
    hudGestureBanner.classList.add("hidden");

    // Clear detections
    resetTargetDisplay();
}

function captureAndSendWebcamFrame() {
    if (!isVisionStreaming || isProcessingFrame || !webcamVideo.videoWidth) return;

    hiddenCtx.drawImage(webcamVideo, 0, 0, hiddenOffscreenCanvas.width, hiddenOffscreenCanvas.height);
    const base64Data = hiddenOffscreenCanvas.toDataURL("image/jpeg", 0.65);

    isProcessingFrame = true;

    fetch("/api/vision/detect", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
            image: base64Data,
            detect_persons: chkPersons.checked,
            detect_small_objects: chkObjects.checked,
            detect_gestures: chkGestures.checked,
            return_annotated: true,
            flip_v: isCameraFlipped,
            flip_h: isCameraFlipped
        })
    })
    .then(res => res.json())
    .then(data => handleVisionResult(data))
    .catch(err => console.error("[Vision REST] Error:", err))
    .finally(() => { isProcessingFrame = false; });
}

function scheduleNextESP32Frame() {
    if (!isVisionStreaming || currentVisionSource !== "esp32") return;
    captureAndSendESP32Frame().then(() => {
        if (isVisionStreaming && currentVisionSource === "esp32") {
            // Adaptive pause: 60ms delay ensures ESP32 camera DMA buffer is refreshed
            visionFrameTimer = setTimeout(scheduleNextESP32Frame, 60);
        }
    });
}

async function captureAndSendESP32Frame() {
    if (!isVisionStreaming || isProcessingFrame) return;

    const espIp = (esp32CamIp.value || "").trim();
    if (!espIp) {
        hudStatus.textContent = "ENTER ESP32 IP";
        return;
    }

    isProcessingFrame = true;

    try {
        const response = await fetch("/api/vision/detect_camera", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                host: espIp,
                detect_persons: chkPersons.checked,
                detect_small_objects: chkObjects.checked,
                detect_gestures: chkGestures.checked,
                return_annotated: true,
                flip_v: isCameraFlipped,
                flip_h: isCameraFlipped
            })
        });
        const data = await response.json();
        if (data && data.success) {
            hudStatus.textContent = "ESP32 CAM ONLINE";
            handleVisionResult(data);
            if (data.annotated_frame) {
                await new Promise((resolve) => {
                    reusableAnnotatedImg.onload = () => {
                        visionCtx.drawImage(reusableAnnotatedImg, 0, 0, visionCanvas.width, visionCanvas.height);
                        resolve();
                    };
                    reusableAnnotatedImg.onerror = resolve;
                    reusableAnnotatedImg.src = data.annotated_frame;
                });
            }
        } else if (data && data.error) {
            hudStatus.textContent = "CAM UNREACHABLE";
            if (hudLiveDot) hudLiveDot.style.background = "#ef4444";
            console.warn("[ESP32 Vision] Camera error:", data.error);
        }
    } catch (err) {
        console.error("[ESP32 Vision] Fetch error:", err);
        hudStatus.textContent = "CAM RETRYING...";
        if (hudLiveDot) hudLiveDot.style.background = "#f59e0b";
    } finally {
        isProcessingFrame = false;
    }
}

function handleVisionResult(result) {
    isProcessingFrame = false;
    if (!result || !result.success) return;

    // Calculate real-time FPS
    frameCounter++;
    const now = performance.now();
    if (now - lastFpsCheck >= 1000) {
        const measuredFps = Math.round((frameCounter * 1000) / (now - lastFpsCheck));
        hudFps.textContent = `${measuredFps}`;
        frameCounter = 0;
        lastFpsCheck = now;
    }

    // Render annotated frame onto canvas if available
    if (result.annotated_frame && currentVisionSource === "webcam") {
        const img = new Image();
        img.onload = () => {
            visionCtx.drawImage(img, 0, 0, visionCanvas.width, visionCanvas.height);
        };
        img.src = result.annotated_frame;
    }

    // Update KPI numbers
    kpiPersons.textContent = result.person_count || 0;
    kpiObjects.textContent = result.small_object_count || 0;
    kpiGestures.textContent = result.gesture_count || 0;

    const totalCount = (result.person_count || 0) + (result.small_object_count || 0) + (result.gesture_count || 0);
    badgeTotalTargets.textContent = `${totalCount} Target${totalCount === 1 ? '' : 's'}`;

    // Handle Active Gesture Banner
    if (result.gestures && result.gestures.length > 0) {
        const topGesture = result.gestures[0];
        const icon = GESTURE_ICONS[topGesture.gesture] || "👋";
        hudGestureIcon.textContent = icon;
        hudGestureName.textContent = `${topGesture.hand} Hand: ${topGesture.friendly_label}`;
        hudGestureConf.textContent = `${Math.round(topGesture.confidence * 100)}%`;
        hudGestureBanner.classList.remove("hidden");

        if (gestureClearTimer) clearTimeout(gestureClearTimer);
        gestureClearTimer = setTimeout(() => {
            hudGestureBanner.classList.add("hidden");
        }, 3000);
    } else {
        if (!gestureClearTimer) {
            hudGestureBanner.classList.add("hidden");
        }
    }

    // Render Target Log Cards in Sidebar
    renderTargetCards(result);
}

function renderTargetCards(result) {
    const cards = [];

    // 1. Persons
    if (result.persons) {
        result.persons.forEach(p => {
            cards.push(`
                <div class="target-card person">
                    <div class="target-info">
                        <span class="target-icon">👤</span>
                        <div>
                            <div class="target-name">Person Detected</div>
                            <div class="target-category">Humanoid Presence</div>
                        </div>
                    </div>
                    <span class="target-score">${Math.round(p.confidence * 100)}%</span>
                </div>
            `);
        });
    }

    // 2. Small Objects
    if (result.small_objects) {
        result.small_objects.forEach(o => {
            const icon = OBJECT_ICONS[o.raw_class] || OBJECT_ICONS[o.label.toLowerCase()] || "📦";
            cards.push(`
                <div class="target-card small-object">
                    <div class="target-info">
                        <span class="target-icon">${icon}</span>
                        <div>
                            <div class="target-name">${o.label}</div>
                            <div class="target-category">Small Object</div>
                        </div>
                    </div>
                    <span class="target-score">${Math.round(o.confidence * 100)}%</span>
                </div>
            `);
        });
    }

    // 3. Hand Gestures
    if (result.gestures) {
        result.gestures.forEach(g => {
            const icon = GESTURE_ICONS[g.gesture] || "👋";
            cards.push(`
                <div class="target-card gesture">
                    <div class="target-info">
                        <span class="target-icon">${icon}</span>
                        <div>
                            <div class="target-name">${g.friendly_label}</div>
                            <div class="target-category">${g.hand} Hand Landmark</div>
                        </div>
                    </div>
                    <span class="target-score">${Math.round(g.confidence * 100)}%</span>
                </div>
            `);
        });
    }

    const newHtml = cards.length > 0 ? cards.join("") : `<div class="detection-empty"><span>Scanning view for targets...</span></div>`;
    if (newHtml !== lastCardsHtml) {
        detectionList.innerHTML = newHtml;
        lastCardsHtml = newHtml;
    }
}

function resetTargetDisplay() {
    kpiPersons.textContent = "0";
    kpiObjects.textContent = "0";
    kpiGestures.textContent = "0";
    badgeTotalTargets.textContent = "0 Targets";
    detectionList.innerHTML = `<div class="detection-empty"><span>Waiting for camera feed activation...</span></div>`;
}

function askIviaVision(question) {
    // Switch to QA tab or send vision prompt directly
    switchMode("general_qa");
    sendPrompt(question);
}

