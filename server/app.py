import os
import sys

# Suppress warnings and redirect Keras cache to writable temp directory
temp_dir = os.environ.get("TEMP", os.environ.get("TMP", "C:\\Temp"))
os.environ["KERAS_HOME"] = os.path.join(temp_dir, "keras")
os.environ["MPLCONFIGDIR"] = os.path.join(temp_dir, "matplotlib_cache")
os.environ["TF_ENABLE_ONEDNN_OPTS"] = "0"
os.environ["TF_CPP_MIN_LOG_LEVEL"] = "3"

import asyncio
import json
import time
from typing import Set
from collections import deque
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel

from server.config import (
    HOST,
    PORT,
    ROBOT_NAME,
    SILENCE_THRESHOLD,
    SILENCE_DURATION_SEC,
    MIN_SPEECH_DURATION_SEC,
    SAMPLE_RATE
)
from server.audio_utils import calculate_rms, pcm_to_wav_bytes
from server.stt_engine import STTEngine
from server.llm_engine import LLMEngine
from server.tts_engine import TTSEngine
from server.vision_engine import VisionEngine
from fastapi.responses import FileResponse, StreamingResponse
import httpx

app = FastAPI(title=f"{ROBOT_NAME} Brain Server")

# Initialize AI Engines
stt_engine = STTEngine()
llm_engine = LLMEngine()
tts_engine = TTSEngine()
vision_engine = VisionEngine()

# Connection pools
esp32_connections: Set[WebSocket] = set()
web_connections: Set[WebSocket] = set()

# Server state
current_mode = "general_qa"  # "general_qa" or "object_detection"
robot_state = "idle"         # "idle", "listening", "processing", "speaking"
speech_cooldown_until = 0.0  # Timestamp until which mic input is quarantined to block speaker echo
last_esp32_ip = ""           # Automatically captured IP address of connected ESP32 node

async def broadcast_to_web(message: dict):
    """Broadcast JSON message to all connected web dashboard clients."""
    if not web_connections:
        return
    data = json.dumps(message)
    dead_connections = set()
    for ws in web_connections:
        try:
            await ws.send_text(data)
        except Exception:
            dead_connections.add(ws)
    for dead in dead_connections:
        web_connections.remove(dead)

async def set_state(new_state: str):
    global robot_state
    robot_state = new_state
    await broadcast_to_web({"event": "state_change", "state": robot_state})

async def stream_pcm_to_esp32(target_ws: WebSocket, pcm_bytes: bytes):
    """
    Stream PCM audio chunks to the ESP32 speaker.
    Can be cancelled instantly by asyncio if user interrupts (barge-in).
    Uses 2048-byte chunks (64ms) to halve TLS packet load and eliminate buffer drops on mobile hotspots.
    """
    global speech_cooldown_until
    try:
        await target_ws.send_text(json.dumps({"event": "speaking_start"}))
        chunk_size = 2048
        for i in range(0, len(pcm_bytes), chunk_size):
            await target_ws.send_bytes(pcm_bytes[i:i+chunk_size])
            await asyncio.sleep(0.050)
        await target_ws.send_text(json.dumps({"event": "speaking_end"}))
    except asyncio.CancelledError:
        print("[Audio Stream] Playback interrupted! Stopping physical speaker.")
        try:
            await target_ws.send_text(json.dumps({"event": "stop_speaking"}))
        except Exception:
            pass
        raise
    finally:
        speech_cooldown_until = time.time() + 1.2
        if robot_state == "speaking":
            await set_state("idle")

# ========================================================
# ESP32 WebSocket Endpoint (Audio Streaming)
# ========================================================
@app.websocket("/ws/esp32")
async def esp32_websocket_endpoint(websocket: WebSocket):
    global robot_state, current_mode, last_esp32_ip
    await websocket.accept()
    esp32_connections.add(websocket)
    last_esp32_ip = websocket.client.host if websocket.client else ""
    print(f"[ESP32] Node connected successfully from {last_esp32_ip}!")
    await broadcast_to_web({"event": "esp32_status", "connected": True, "ip": last_esp32_ip})

    # Audio stream buffer & VAD variables
    audio_buffer = bytearray()
    preroll_buffer = deque(maxlen=35)  # Preserves ~560ms of speech onset so first syllable is never cut
    is_user_speaking = False
    silence_start_time = None
    speech_start_time = None

    last_audio_log = 0.0
    last_interaction_time = time.time()
    is_standby = False
    interrupt_counter = 0
    current_speech_task: asyncio.Task = None

    try:
        while True:
            # Receive either binary PCM audio or JSON control text
            message = await websocket.receive()
            
            if "bytes" in message and message["bytes"]:
                pcm_chunk = message["bytes"]
                rms = calculate_rms(pcm_chunk)
                now = time.time()

                # Emit audio level to web visualizer
                await broadcast_to_web({"event": "audio_level", "rms": rms})

                # --- 1. ECHO PREVENTION: WHILE SPEAKING OR DURING POST-SPEECH COOLDOWN (1.2s) ---
                if robot_state == "speaking" or now < speech_cooldown_until:
                    # Flush buffers completely so speaker sound never loops back as user speech
                    preroll_buffer.clear()
                    audio_buffer.clear()
                    is_user_speaking = False
                    silence_start_time = None
                    speech_start_time = None
                    continue

                # Keep rolling pre-roll buffer of incoming user audio
                preroll_buffer.append(pcm_chunk)

                # --- 2. 10-SECOND INACTIVITY SILENCE / STANDBY ---
                if not is_user_speaking and robot_state == "idle":
                    if (now - last_interaction_time) > 10.0 and not is_standby:
                        is_standby = True
                        print("[System] IVIA entered silent standby (> 10s inactivity). Waiting for new speech...")
                        await broadcast_to_web({"event": "standby", "active": True})

                # Print audio level debug every 3 seconds so user can see mic activity
                if now - last_audio_log > 3.0:
                    last_audio_log = now
                    state_str = "STANDBY" if is_standby else ("LISTENING" if is_user_speaking else "IDLE")
                    print(f"[Mic Stream] State: {state_str} | RMS: {int(rms)} | Threshold: {SILENCE_THRESHOLD}")

                speech_start_threshold = SILENCE_THRESHOLD
                speech_continue_threshold = int(SILENCE_THRESHOLD * 0.75)

                if not is_user_speaking:
                    if rms > speech_start_threshold:
                        is_user_speaking = True
                        is_standby = False
                        last_interaction_time = now
                        speech_start_time = now
                        silence_start_time = None
                        audio_buffer.clear()
                        # Prepend the pre-roll audio so the start of words is never clipped!
                        for past_chunk in preroll_buffer:
                            audio_buffer.extend(past_chunk)
                        await set_state("listening")
                        print(f"[VAD] Voice detected (RMS: {int(rms)})! Listening...")
                else:
                    # User is actively speaking
                    audio_buffer.extend(pcm_chunk)
                    speech_duration = (now - speech_start_time)

                    if rms > speech_continue_threshold:
                        silence_start_time = None
                    else:
                        if silence_start_time is None:
                            silence_start_time = now

                    silence_elapsed = (now - silence_start_time) if silence_start_time else 0.0

                    # End of speech condition: pause duration exceeded OR max speech cap (15s)
                    if silence_elapsed >= SILENCE_DURATION_SEC or speech_duration >= 15.0:
                        print(f"[VAD] End of speech detected ({speech_duration:.1f}s speech, {silence_elapsed:.1f}s pause). Processing...")
                        
                        is_user_speaking = False
                        silence_start_time = None
                        speech_start_time = None
                        last_interaction_time = now

                        if speech_duration >= MIN_SPEECH_DURATION_SEC and len(audio_buffer) > 4000:
                            await set_state("processing")
                            wav_data = pcm_to_wav_bytes(bytes(audio_buffer))
                            audio_buffer.clear()
                            preroll_buffer.clear()

                            # Save debug recording to workspace
                            try:
                                with open("debug_last_voice.wav", "wb") as f:
                                    f.write(wav_data)
                            except Exception:
                                pass

                            # Run STT in threadpool
                            user_text = await asyncio.to_thread(stt_engine.transcribe, wav_data)
                            if user_text:
                                await broadcast_to_web({"event": "transcript", "role": "user", "text": user_text})
                                
                                # Process query through LLM with real-time visual sensor context
                                visual_ctx = vision_engine.get_visual_context_summary()
                                answer_text = await asyncio.to_thread(llm_engine.generate_response, user_text, visual_ctx)
                                await broadcast_to_web({"event": "transcript", "role": "ivia", "text": answer_text})

                                # Synthesize Speech
                                await set_state("speaking")
                                pcm_out = await tts_engine.synthesize_to_pcm(answer_text)
                                if pcm_out:
                                    if current_speech_task and not current_speech_task.done():
                                        current_speech_task.cancel()
                                    current_speech_task = asyncio.create_task(stream_pcm_to_esp32(websocket, pcm_out))
                                else:
                                    await set_state("idle")
                            else:
                                print("[VAD] No discernible words detected.")
                                await set_state("idle")
                        else:
                            audio_buffer.clear()
                            await set_state("idle")

            elif "text" in message and message["text"]:
                try:
                    payload = json.loads(message["text"])
                    print(f"[ESP32 Event] {payload}")
                except Exception:
                    pass

    except WebSocketDisconnect:
        print("[ESP32] Disconnected.")
    except Exception as e:
        print(f"[ESP32] Error: {e}")
    finally:
        if current_speech_task and not current_speech_task.done():
            current_speech_task.cancel()
        esp32_connections.discard(websocket)
        await broadcast_to_web({"event": "esp32_status", "connected": len(esp32_connections) > 0})
        await set_state("idle")

# ========================================================
# Web Dashboard WebSocket Endpoint
# ========================================================
@app.websocket("/ws/web")
async def web_websocket_endpoint(websocket: WebSocket):
    global current_mode, robot_state
    await websocket.accept()
    web_connections.add(websocket)

    # Initial state handshake
    await websocket.send_text(json.dumps({
        "event": "init",
        "esp32_connected": len(esp32_connections) > 0,
        "esp32_ip": last_esp32_ip,
        "mode": current_mode,
        "state": robot_state,
        "robot_name": ROBOT_NAME
    }))

    try:
        while True:
            data = await websocket.receive_text()
            message = json.loads(data)
            action = message.get("action")

            if action == "set_mode":
                new_mode = message.get("mode", "general_qa")
                if new_mode != current_mode:
                    current_mode = new_mode
                    await broadcast_to_web({"event": "mode_changed", "mode": current_mode})
                    print(f"[System] Switched mode to: {current_mode}")

            elif action == "chat":
                # User typed a question directly from the web interface
                user_text = message.get("text", "").strip()
                if user_text:
                    await broadcast_to_web({"event": "transcript", "role": "user", "text": user_text})
                    await set_state("processing")

                    visual_ctx = vision_engine.get_visual_context_summary()
                    answer_text = await asyncio.to_thread(llm_engine.generate_response, user_text, visual_ctx)
                    await broadcast_to_web({"event": "transcript", "role": "ivia", "text": answer_text})

                    # If ESP32 is connected, also stream audio to physical robot speaker!
                    await set_state("speaking")
                    pcm_out = await tts_engine.synthesize_to_pcm(answer_text)

                    # Send to connected ESP32s
                    for esp_ws in list(esp32_connections):
                        try:
                            await esp_ws.send_text(json.dumps({"event": "speaking_start"}))
                            chunk_size = 1024
                            for i in range(0, len(pcm_out), chunk_size):
                                await esp_ws.send_bytes(pcm_out[i:i+chunk_size])
                                await asyncio.sleep(0.025)
                            await esp_ws.send_text(json.dumps({"event": "speaking_end"}))
                        except Exception:
                            pass

                    # Only stream to laptop/browser speaker if NO physical ESP32 speaker is connected
                    if pcm_out and len(esp32_connections) == 0:
                        await websocket.send_bytes(pcm_out)

                    global speech_cooldown_until
                    speech_cooldown_until = time.time() + 1.2
                    await set_state("idle")

            elif action == "vision_frame":
                # Real-time frame processing from web client
                image_data = message.get("image")
                detect_persons = message.get("detect_persons", True)
                detect_small_objects = message.get("detect_small_objects", True)
                detect_gestures = message.get("detect_gestures", True)
                return_annotated = message.get("return_annotated", True)

                if image_data:
                    res = await asyncio.to_thread(
                        vision_engine.process_frame,
                        image_data,
                        detect_persons,
                        detect_small_objects,
                        detect_gestures,
                        return_annotated
                    )
                    await websocket.send_text(json.dumps({
                        "event": "vision_result",
                        "data": res
                    }))

    except WebSocketDisconnect:
        pass
    except Exception as e:
        print(f"[Web WS] Error: {e}")
    finally:
        web_connections.discard(websocket)

# ========================================================
# REST Endpoints & Web UI Static Hosting
# ========================================================
@app.get("/api/status")
async def get_status():
    return {
        "status": "online",
        "robot_name": ROBOT_NAME,
        "esp32_connected": len(esp32_connections) > 0,
        "esp32_ip": last_esp32_ip,
        "web_clients": len(web_connections),
        "mode": current_mode,
        "state": robot_state
    }

class ChatRequest(BaseModel):
    message: str

@app.post("/api/chat")
async def rest_chat(request: ChatRequest):
    user_text = request.message.strip()
    if not user_text:
        return {"error": "Empty message"}
    visual_ctx = vision_engine.get_visual_context_summary()
    reply = await asyncio.to_thread(llm_engine.generate_response, user_text, visual_ctx)
    return {"reply": reply}

# --- Vision Endpoints ---
class VisionDetectRequest(BaseModel):
    image: str
    detect_persons: bool = True
    detect_small_objects: bool = True
    detect_gestures: bool = True
    return_annotated: bool = True
    flip_v: bool = False
    flip_h: bool = False

@app.post("/api/vision/detect")
async def api_detect_vision(req: VisionDetectRequest):
    res = await asyncio.to_thread(
        vision_engine.process_frame,
        req.image,
        req.detect_persons,
        req.detect_small_objects,
        req.detect_gestures,
        req.return_annotated,
        req.flip_v,
        req.flip_h
    )
    return res

@app.get("/api/vision/context")
async def api_vision_context():
    return {
        "summary": vision_engine.get_visual_context_summary(),
        "last_persons": vision_engine.last_detected_persons,
        "last_objects": vision_engine.last_detected_objects,
        "last_gestures": vision_engine.last_detected_gestures,
        "timestamp": vision_engine.last_detection_time
    }

def sanitize_host_port(host_str: str, default_port: int = 80) -> tuple[str, int]:
    """Cleans up host string by removing http://, trailing slashes, and extracting port."""
    h = (host_str or "").strip()
    h = h.replace("http://", "").replace("https://", "").strip().rstrip("/")
    p = default_port
    if ":" in h:
        parts = h.split(":")
        h = parts[0]
        try:
            p = int(parts[1])
        except (ValueError, IndexError):
            pass
    return h, p

@app.get("/api/camera/stream")
async def api_camera_proxy(host: str = "192.168.1.100", port: int = 80):
    """
    Proxies live MJPEG stream from the ESP32 OV3660 camera directly to the browser.
    Eliminates CORS and browser mixed-content restrictions.
    """
    clean_host, clean_port = sanitize_host_port(host, port)
    url = f"http://{clean_host}:{clean_port}/stream"

    async def stream_generator():
        async with httpx.AsyncClient(timeout=30.0) as client:
            target_url = url
            # Check if /stream is available; if not, try root /
            try:
                r = await client.head(url, timeout=2.0)
                if r.status_code == 404:
                    target_url = f"http://{clean_host}:{clean_port}/"
            except Exception:
                pass

            try:
                async with client.stream("GET", target_url) as resp:
                    async for chunk in resp.aiter_raw():
                        yield chunk
            except Exception as e:
                print(f"[Camera Proxy] Stream error: {e}")

    return StreamingResponse(
        stream_generator(),
        media_type="multipart/x-mixed-replace; boundary=123456789000000000000987654321"
    )

@app.get("/api/camera/capture")
async def api_camera_capture(host: str = "192.168.29.55", port: int = 80):
    """Fetches a single JPEG frame snapshot from ESP32 OV3660 camera."""
    clean_host, clean_port = sanitize_host_port(host, port)
    url = f"http://{clean_host}:{clean_port}/capture"
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get(url)
            if resp.status_code == 200:
                from fastapi.responses import Response
                return Response(content=resp.content, media_type="image/jpeg")
            return {"error": f"Camera returned status {resp.status_code}"}
    except Exception as e:
        return {"error": str(e)}

class CameraDetectRequest(BaseModel):
    host: str
    port: int = 80
    detect_persons: bool = True
    detect_small_objects: bool = True
    detect_gestures: bool = True
    return_annotated: bool = True
    flip_v: bool = False
    flip_h: bool = False

@app.post("/api/vision/detect_camera")
async def api_detect_camera(req: CameraDetectRequest):
    """Fetches snapshot directly from ESP32 camera and runs YOLO + MediaPipe detection."""
    clean_host, clean_port = sanitize_host_port(req.host, req.port)
    url = f"http://{clean_host}:{clean_port}/capture"
    try:
        async with httpx.AsyncClient(timeout=8.0) as client:
            resp = await client.get(url)
            if resp.status_code == 200:
                res = await asyncio.to_thread(
                    vision_engine.process_frame,
                    resp.content,
                    req.detect_persons,
                    req.detect_small_objects,
                    req.detect_gestures,
                    req.return_annotated,
                    req.flip_v,
                    req.flip_h
                )
                return res
            return {"success": False, "error": f"Camera returned HTTP {resp.status_code}"}
    except Exception as e:
        err_msg = str(e).strip() or type(e).__name__
        return {"success": False, "error": f"Failed to connect to ESP32 camera at {url}: {err_msg}"}

# Mount Web Dashboard
app.mount("/static", StaticFiles(directory="web"), name="static")

@app.get("/")
async def serve_index():
    return FileResponse("web/index.html")
