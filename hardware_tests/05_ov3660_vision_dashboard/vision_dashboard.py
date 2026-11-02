"""
IVIA Vision Dashboard: Standalone Object & Gesture Detection
Connects to ESP32-S3 OV3660 Camera Node over Wi-Fi
Runs YOLOv8 Object Detection + MediaPipe Gesture Recognizer (Tasks API)
Generates real-time "What it says" live text narration
"""

import sys
import os
import time
import argparse
import requests
import numpy as np
import cv2

# ==============================================================================
# 0. SUPPRESS NOISY WARNINGS & C++ LOGS BEFORE IMPORTS
# ==============================================================================
temp_dir = os.environ.get("TEMP", os.environ.get("TMP", "C:\\Temp"))
os.environ["MPLCONFIGDIR"] = os.path.join(temp_dir, "matplotlib_cache")
os.environ["TF_ENABLE_ONEDNN_OPTS"] = "0"
os.environ["TF_CPP_MIN_LOG_LEVEL"] = "3"
os.environ["GLOG_minloglevel"] = "3"
os.environ["ABSL_LOG_PREFIX"] = "0"

script_dir = os.path.dirname(os.path.abspath(__file__))
model_path = os.path.join(script_dir, "gesture_recognizer.task")
if not os.path.exists(model_path):
    parent_path = os.path.join(script_dir, "..", "..", "gesture_recognizer.task")
    if os.path.exists(parent_path):
        model_path = os.path.abspath(parent_path)

# Redirect C-level stderr during model imports and initialization to eliminate all warning/error codes
try:
    stderr_fd = sys.stderr.fileno()
    null_fd = os.open(os.devnull, os.O_WRONLY)
    saved_stderr = os.dup(stderr_fd)
    os.dup2(null_fd, stderr_fd)
except Exception:
    saved_stderr = None

try:
    from ultralytics import YOLO
    import mediapipe as mp
    from mediapipe.tasks import python
    from mediapipe.tasks.python import vision
    from mediapipe.tasks.python.vision import HandLandmarksConnections, GestureRecognizer

    # Fix Python 3.13 MediaPipe destructor exit bug
    def _safe_del(self):
        try:
            self.close()
        except Exception:
            pass
    GestureRecognizer.__del__ = _safe_del

    base_options = python.BaseOptions(model_asset_path=model_path)
    gesture_options = vision.GestureRecognizerOptions(
        base_options=base_options,
        num_hands=2,
        min_hand_detection_confidence=0.5,
        min_hand_presence_confidence=0.5,
        min_tracking_confidence=0.5,
    )
    gesture_recognizer = vision.GestureRecognizer.create_from_options(gesture_options)

finally:
    # Restore stderr
    if saved_stderr is not None:
        try:
            os.dup2(saved_stderr, stderr_fd)
            os.close(saved_stderr)
            os.close(null_fd)
        except Exception:
            pass

# ==============================================================================
# 1. PARSE ARGUMENTS & SANITIZE IP
# ==============================================================================
DEFAULT_ESP32_IP = "10.35.199.118"

parser = argparse.ArgumentParser(description="IVIA OV3660 Vision Dashboard")
parser.add_argument("--ip", default=DEFAULT_ESP32_IP, help="ESP32-S3 IP Address (e.g. 10.35.199.118)")
parser.add_argument("--use-webcam", action="store_true", help="Fallback to PC local webcam")
parser.add_argument("--conf", type=float, default=0.38, help="YOLO confidence threshold (default 0.38)")
args = parser.parse_args()

# Clean up input IP (handles 'http://10.35.199.118/', '10.35.199.118', etc.)
raw_ip = args.ip.strip()
if "://" in raw_ip:
    raw_ip = raw_ip.split("://")[1]
raw_ip = raw_ip.split("/")[0]
ESP32_IP = raw_ip

STREAM_URL = f"http://{ESP32_IP}/stream"
CAPTURE_URL = f"http://{ESP32_IP}/capture"

print("=" * 60)
print("  IVIA OV3660 STANDALONE VISION DASHBOARD")
print("  Objects (YOLOv8) + Gestures (MediaPipe) + Narration")
print(f"  Target Node: http://{ESP32_IP}")
print("=" * 60)

# ==============================================================================
# 2. INITIALIZE AI MODELS
# ==============================================================================
print("[AI] Loading YOLOv8 model...")
yolo_model = YOLO("yolov8n.pt")
print("[AI] Models loaded successfully!")

GESTURE_MAP = {
    "Thumb_Up": "Thumbs Up",
    "Thumb_Down": "Thumbs Down",
    "Open_Palm": "Open Hand (Wave / Stop)",
    "Closed_Fist": "Fist",
    "Pointing_Up": "Pointing",
    "Victory": "Peace / Victory (V)",
    "ILoveYou": "I Love You",
}

# ==============================================================================
# 3. DRAWING & NARRATION HELPERS
# ==============================================================================
def draw_hand_skeleton(frame, landmarks, w, h):
    """Draws hand skeleton connections and landmark points."""
    points = [(int(lm.x * w), int(lm.y * h)) for lm in landmarks]
    for conn in HandLandmarksConnections.HAND_CONNECTIONS:
        pt1 = points[conn.start]
        pt2 = points[conn.end]
        cv2.line(frame, pt1, pt2, (255, 230, 0), 2, cv2.LINE_AA)
    for pt in points:
        cv2.circle(frame, pt, 3, (0, 0, 255), -1, cv2.LINE_AA)

def generate_narration(objects, gestures):
    """Synthesizes detected objects and gestures into a live natural sentence."""
    parts = []
    if objects:
        counts = {}
        for obj in objects:
            counts[obj] = counts.get(obj, 0) + 1
        obj_tokens = [f"{count} {name}" if count > 1 else f"a {name}" for name, count in sorted(counts.items(), key=lambda x: -x[1])]
        parts.append("I see " + ", ".join(obj_tokens))

    if gestures:
        unique_gestures = list(dict.fromkeys(gestures))
        parts.append("Gesture: " + ", ".join(unique_gestures))

    if not parts:
        return "Scanning scene... No objects or hands detected."
    return " | ".join(parts)

# ==============================================================================
# 4. VIDEO SOURCE SETUP
# ==============================================================================
cap = None
if args.use_webcam:
    print("[INFO] Using local PC webcam...")
    cap = cv2.VideoCapture(0)
else:
    print(f"[INFO] Connecting to ESP32-S3 live stream at {STREAM_URL}...")
    cap = cv2.VideoCapture(STREAM_URL)
    time.sleep(1.0)
    if not cap.isOpened() or not cap.grab():
        print("[WARN] MJPEG stream endpoint not answering. Will poll /capture endpoint...")
        if cap:
            cap.release()
        cap = None
    else:
        print("[INFO] Connected to ESP32-S3 live stream!")

# ==============================================================================
# 5. MAIN DETECTION LOOP
# ==============================================================================
last_narration = ""
last_log_time = 0
fps_history = []
flip_horizontal = False
session_http = requests.Session()

# Detection smoothing buffers
recent_gestures = []
gesture_hold_counter = 0

print("\n[READY] Vision Dashboard is running!")
print("Controls:")
print("  - Press 'q' to Quit")
print("  - Press 's' to Save snapshot")
print("  - Press 'f' to Flip image horizontally")
print("-" * 60)

try:
    while True:
        start_t = time.time()
        frame = None

        # Fetch frame
        if cap and cap.isOpened():
            ret, frame = cap.read()
            if not ret or frame is None:
                frame = None

        if frame is None and not args.use_webcam:
            try:
                resp = session_http.get(CAPTURE_URL, timeout=1.5)
                if resp.status_code == 200:
                    img_buf = np.frombuffer(resp.content, dtype=np.uint8)
                    frame = cv2.imdecode(img_buf, cv2.IMREAD_COLOR)
            except Exception:
                frame = None

        # Reconnection notice if frame is missing
        if frame is None:
            canvas = np.zeros((480, 640, 3), dtype=np.uint8)
            cv2.putText(canvas, "CONNECTING TO ESP32-S3...", (120, 220), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 200, 255), 2)
            cv2.putText(canvas, f"Target IP: {ESP32_IP}", (120, 260), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (180, 180, 180), 1)
            cv2.putText(canvas, "Verify ESP32 is powered on & on same Wi-Fi", (100, 300), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (100, 100, 255), 1)
            cv2.imshow("IVIA Vision Dashboard - OV3660", canvas)
            if cv2.waitKey(200) & 0xFF == ord('q'):
                break
            continue

        if flip_horizontal:
            frame = cv2.flip(frame, 1)

        h, w, _ = frame.shape
        detected_objects = []
        raw_gestures = []

        # ---------------- A. YOLOv8 Object Detection ----------------
        yolo_results = yolo_model(frame, conf=args.conf, verbose=False)[0]
        for box in yolo_results.boxes:
            conf = float(box.conf[0])
            cls_id = int(box.cls[0])
            label = yolo_model.names[cls_id]
            detected_objects.append(label)

            x1, y1, x2, y2 = map(int, box.xyxy[0])
            cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 245, 155), 2)
            
            tag_text = f"{label} {int(conf * 100)}%"
            (tw, th), _ = cv2.getTextSize(tag_text, cv2.FONT_HERSHEY_SIMPLEX, 0.5, 1)
            cv2.rectangle(frame, (x1, max(0, y1 - 22)), (x1 + tw + 8, y1), (0, 245, 155), -1)
            cv2.putText(frame, tag_text, (x1 + 4, y1 - 6), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 0), 1, cv2.LINE_AA)

        # ---------------- B. MediaPipe Gesture Recognition ----------------
        rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        rgb_contiguous = np.ascontiguousarray(rgb_frame)
        mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb_contiguous)
        recognition_result = gesture_recognizer.recognize(mp_image)

        if recognition_result.hand_landmarks:
            for idx, hand_lms in enumerate(recognition_result.hand_landmarks):
                draw_hand_skeleton(frame, hand_lms, w, h)
                
                # Check gesture for this hand
                if idx < len(recognition_result.gestures) and recognition_result.gestures[idx]:
                    top_gesture = recognition_result.gestures[idx][0]
                    cat_name = top_gesture.category_name
                    if cat_name and cat_name != "None":
                        display_name = GESTURE_MAP.get(cat_name, cat_name)
                        raw_gestures.append(display_name)
                        
                        # Show gesture tag above wrist
                        wrist = hand_lms[0]
                        wx, wy = int(wrist.x * w), int(wrist.y * h)
                        cv2.putText(frame, f"{display_name} ({int(top_gesture.score * 100)}%)",
                                    (max(10, wx - 40), max(30, wy + 35)),
                                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 0), 2, cv2.LINE_AA)

        # Gesture persistence / smoothing (hold gesture for 6 frames so it doesn't flicker)
        if raw_gestures:
            recent_gestures = raw_gestures
            gesture_hold_counter = 6
        elif gesture_hold_counter > 0:
            gesture_hold_counter -= 1
        else:
            recent_gestures = []

        # ---------------- C. 'What it says' Narration ----------------
        narration = generate_narration(detected_objects, recent_gestures)

        now = time.time()
        if narration != last_narration and (now - last_log_time) > 1.2:
            print(f"[WHAT IT SAYS] >>> {narration}")
            last_narration = narration
            last_log_time = now

        # ---------------- D. Dashboard Overlays ----------------
        # Top banner: "What it says"
        cv2.rectangle(frame, (0, 0), (w, 54), (15, 23, 42), -1)
        cv2.line(frame, (0, 54), (w, 54), (0, 245, 155), 2)
        cv2.putText(frame, "WHAT IT SAYS:", (12, 20), cv2.FONT_HERSHEY_SIMPLEX, 0.42, (0, 229, 255), 1, cv2.LINE_AA)
        cv2.putText(frame, narration, (12, 44), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (255, 255, 255), 1, cv2.LINE_AA)

        # Bottom status bar
        dt = time.time() - start_t
        fps = 1.0 / dt if dt > 0 else 0
        fps_history.append(fps)
        if len(fps_history) > 15:
            fps_history.pop(0)
        avg_fps = sum(fps_history) / len(fps_history)

        cv2.rectangle(frame, (0, h - 26), (w, h), (15, 23, 42), -1)
        status_str = f"ESP32: {ESP32_IP}  |  Res: {w}x{h}  |  FPS: {avg_fps:.1f}  |  's': Snapshot, 'q': Quit"
        cv2.putText(frame, status_str, (10, h - 8), cv2.FONT_HERSHEY_SIMPLEX, 0.42, (148, 163, 184), 1, cv2.LINE_AA)

        cv2.imshow("IVIA Vision Dashboard - OV3660", frame)

        key = cv2.waitKey(1) & 0xFF
        if key == ord('q'):
            break
        elif key == ord('s'):
            filename = f"capture_{int(time.time())}.jpg"
            cv2.imwrite(filename, frame)
            print(f"[SNAPSHOT] Saved image to {filename}")
        elif key == ord('f'):
            flip_horizontal = not flip_horizontal
            print(f"[INFO] Flip horizontal: {flip_horizontal}")

finally:
    if cap:
        cap.release()
    cv2.destroyAllWindows()
    try:
        gesture_recognizer.close()
    except Exception:
        pass
    print("\n[INFO] Dashboard closed.")
