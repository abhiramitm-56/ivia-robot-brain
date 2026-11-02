import os
import sys

# Suppress warnings and redirect Keras / Matplotlib cache to writable temp directory
temp_dir = os.environ.get("TEMP", os.environ.get("TMP", "C:\\Temp"))
os.environ["KERAS_HOME"] = os.path.join(temp_dir, "keras")
os.environ["MPLCONFIGDIR"] = os.path.join(temp_dir, "matplotlib_cache")
os.environ["TF_ENABLE_ONEDNN_OPTS"] = "0"
os.environ["TF_CPP_MIN_LOG_LEVEL"] = "3"

import cv2
import numpy as np
import base64
import time
from typing import Dict, Any, List, Optional
from ultralytics import YOLO
import mediapipe as mp
from mediapipe.tasks import python
from mediapipe.tasks.python import vision
from mediapipe.tasks.python.vision import GestureRecognizer

# Fix Python 3.13 MediaPipe destructor exit bug
def _safe_del(self):
    try:
        self.close()
    except Exception:
        pass
GestureRecognizer.__del__ = _safe_del

# COCO small object categories of interest
SMALL_OBJECT_CLASSES = {
    "bottle", "wine glass", "cup", "fork", "knife", "spoon", "bowl",
    "banana", "apple", "sandwich", "orange", "broccoli", "carrot",
    "hot dog", "pizza", "donut", "cake", "laptop", "mouse", "remote",
    "keyboard", "cell phone", "microwave", "oven", "toaster", "sink",
    "book", "clock", "vase", "scissors", "teddy bear", "hair drier",
    "toothbrush", "backpack", "umbrella", "handbag", "tie", "suitcase"
}

GESTURE_FRIENDLY_NAMES = {
    "Closed_Fist": "✊ Closed Fist",
    "Open_Palm": "🖐️ Open Palm / Wave",
    "Pointing_Up": "☝️ Pointing Up",
    "Thumb_Down": "👎 Thumbs Down",
    "Thumb_Up": "👍 Thumbs Up",
    "Victory": "✌️ Peace / Victory",
    "ILoveYou": "🤟 I Love You",
    "OK_Sign": "👌 OK Sign",
    "Pinch": "🤏 Pinch",
    "Rock_On": "🤘 Rock On",
    "None": "Hand Detected",
    "Unrecognized": "Hand Detected"
}

# MediaPipe Hand Connections for skeleton lines (21 landmarks)
HAND_CONNECTIONS = [
    (0, 1), (1, 2), (2, 3), (3, 4),        # Thumb
    (0, 5), (5, 6), (6, 7), (7, 8),        # Index
    (5, 9), (9, 10), (10, 11), (11, 12),   # Middle
    (9, 13), (13, 14), (14, 15), (15, 16), # Ring
    (13, 17), (17, 18), (18, 19), (19, 20),# Pinky
    (0, 17)                                # Palm base
]

class VisionEngine:
    def __init__(self, yolo_model_path: str = "yolov8n.pt", gesture_model_path: str = "gesture_recognizer.task"):
        print("[VisionEngine] Initializing YOLO and MediaPipe Gesture models...")
        self.yolo = YOLO(yolo_model_path)
        
        base_options = python.BaseOptions(model_asset_path=gesture_model_path)
        options = vision.GestureRecognizerOptions(
            base_options=base_options,
            num_hands=2,
            min_hand_detection_confidence=0.5,
            min_hand_presence_confidence=0.5,
            min_tracking_confidence=0.5
        )
        self.gesture_recognizer = vision.GestureRecognizer.create_from_options(options)

        # Rolling state
        self.last_detection_time = 0.0
        self.last_detected_persons = 0
        self.last_detected_objects: List[str] = []
        self.last_detected_gestures: List[str] = []
        self.last_summary = "No visual targets detected yet."
        print("[VisionEngine] Vision models loaded successfully!")

    def _refine_custom_gestures(self, landmarks_list, standard_gesture: str) -> str:
        """
        Calculates geometric relationships between hand landmarks to refine gestures like OK sign, pinch, etc.
        landmarks: 21 points with x, y, z normalized [0, 1]
        """
        if not landmarks_list or len(landmarks_list) < 21:
            return standard_gesture

        # Landmark indices
        # 4: Thumb Tip, 8: Index Tip, 12: Middle Tip, 16: Ring Tip, 20: Pinky Tip
        # 6: Index PIP, 10: Middle PIP, 14: Ring PIP, 18: Pinky PIP
        thumb_tip = np.array([landmarks_list[4].x, landmarks_list[4].y])
        index_tip = np.array([landmarks_list[8].x, landmarks_list[8].y])
        middle_tip = np.array([landmarks_list[12].x, landmarks_list[12].y])
        ring_tip = np.array([landmarks_list[16].x, landmarks_list[16].y])
        pinky_tip = np.array([landmarks_list[20].x, landmarks_list[20].y])

        index_pip = np.array([landmarks_list[6].x, landmarks_list[6].y])
        middle_pip = np.array([landmarks_list[10].x, landmarks_list[10].y])
        ring_pip = np.array([landmarks_list[14].x, landmarks_list[14].y])
        pinky_pip = np.array([landmarks_list[18].x, landmarks_list[18].y])

        thumb_index_dist = np.linalg.norm(thumb_tip - index_tip)

        # Check if fingers are extended (tip.y < pip.y assuming hand pointing upwards)
        index_extended = index_tip[1] < index_pip[1]
        middle_extended = middle_tip[1] < middle_pip[1]
        ring_extended = ring_tip[1] < ring_pip[1]
        pinky_extended = pinky_tip[1] < pinky_pip[1]

        # 1. OK Sign: Thumb and Index tips touch, Middle + Ring + Pinky extended
        if thumb_index_dist < 0.05 and middle_extended and ring_extended and pinky_extended:
            return "OK_Sign"

        # 2. Pinch: Thumb and Index tips touch or close, but others not extended
        if thumb_index_dist < 0.04 and not (middle_extended and ring_extended and pinky_extended):
            return "Pinch"

        # 3. Rock On: Index and Pinky extended, Middle and Ring folded
        if index_extended and pinky_extended and not middle_extended and not ring_extended:
            return "Rock_On"

        return standard_gesture

    def process_frame(
        self,
        image_input: Any,
        detect_persons: bool = True,
        detect_small_objects: bool = True,
        detect_gestures: bool = True,
        return_annotated: bool = True,
        flip_v: bool = False,
        flip_h: bool = False
    ) -> Dict[str, Any]:
        """
        Process a single image frame (numpy array or raw bytes or base64 string).
        Returns detection results, counts, bounding boxes, gestures, and annotated image.
        """
        # 1. Decode image input to OpenCV BGR numpy array
        if isinstance(image_input, str):
            if image_input.startswith("data:image"):
                image_input = image_input.split(",", 1)[1]
            img_bytes = base64.b64decode(image_input)
            nparr = np.frombuffer(img_bytes, np.uint8)
            frame = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        elif isinstance(image_input, bytes):
            nparr = np.frombuffer(image_input, np.uint8)
            frame = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        elif isinstance(image_input, np.ndarray):
            frame = image_input.copy()
        else:
            raise ValueError(f"Unsupported image input type: {type(image_input)}")

        if frame is None or frame.size == 0:
            return {"success": False, "error": "Invalid or empty image frame"}

        # Optional orientation correction
        if flip_v and flip_h:
            frame = cv2.flip(frame, -1)  # 180 degree rotation
        elif flip_v:
            frame = cv2.flip(frame, 0)   # Vertical flip
        elif flip_h:
            frame = cv2.flip(frame, 1)   # Horizontal flip

        h, w = frame.shape[:2]
        annotated = frame.copy() if return_annotated else None

        persons: List[Dict[str, Any]] = []
        small_objects: List[Dict[str, Any]] = []
        gestures: List[Dict[str, Any]] = []

        # 2. Run YOLO Object Detection (Persons and Small Things)
        if detect_persons or detect_small_objects:
            try:
                results = self.yolo(frame, verbose=False, conf=0.35)
                for r in results:
                    boxes = r.boxes
                    for box in boxes:
                        cls_id = int(box.cls[0])
                        class_name = self.yolo.names[cls_id]
                        conf = float(box.conf[0])
                        xyxy = box.xyxy[0].cpu().numpy().astype(int).tolist()
                        x1, y1, x2, y2 = xyxy

                        if class_name == "person" and detect_persons:
                            persons.append({
                                "label": "Person",
                                "confidence": round(conf, 2),
                                "bbox": [x1, y1, x2, y2]
                            })
                            if return_annotated:
                                self._draw_cyber_box(
                                    annotated, x1, y1, x2, y2,
                                    label=f"PERSON {int(conf*100)}%",
                                    color=(254, 242, 0) # Neon Cyan in BGR: (B=254, G=242, R=0)
                                )

                        elif class_name in SMALL_OBJECT_CLASSES and detect_small_objects:
                            friendly_label = class_name.replace("_", " ").title()
                            small_objects.append({
                                "label": friendly_label,
                                "raw_class": class_name,
                                "confidence": round(conf, 2),
                                "bbox": [x1, y1, x2, y2]
                            })
                            if return_annotated:
                                self._draw_cyber_box(
                                    annotated, x1, y1, x2, y2,
                                    label=f"{friendly_label.upper()} {int(conf*100)}%",
                                    color=(155, 245, 0) # Neon Emerald in BGR: (B=155, G=245, R=0)
                                )
            except Exception as e:
                print(f"[VisionEngine] YOLO error: {e}")

        # 3. Run MediaPipe Hand Gesture Recognition
        if detect_gestures:
            try:
                rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb_frame)
                recognition_result = self.gesture_recognizer.recognize(mp_image)

                if recognition_result.gestures:
                    for i, gesture_list in enumerate(recognition_result.gestures):
                        if not gesture_list:
                            continue

                        top_gesture = gesture_list[0]
                        gesture_name = top_gesture.category_name
                        confidence = top_gesture.score

                        handedness = "Hand"
                        if i < len(recognition_result.handedness) and recognition_result.handedness[i]:
                            handedness = recognition_result.handedness[i][0].category_name

                        landmarks = []
                        if i < len(recognition_result.hand_landmarks):
                            raw_lm = recognition_result.hand_landmarks[i]
                            # Refine with custom geometry
                            gesture_name = self._refine_custom_gestures(raw_lm, gesture_name)
                            landmarks = [{"x": round(lm.x, 3), "y": round(lm.y, 3), "z": round(lm.z, 3)} for lm in raw_lm]

                        friendly = GESTURE_FRIENDLY_NAMES.get(gesture_name, f"👋 {gesture_name}")

                        # Calculate hand bounding box from landmarks
                        if landmarks:
                            xs = [int(p["x"] * w) for p in landmarks]
                            ys = [int(p["y"] * h) for p in landmarks]
                            hx1, hy1 = max(0, min(xs) - 15), max(0, min(ys) - 15)
                            hx2, hy2 = min(w, max(xs) + 15), min(h, max(ys) + 15)
                        else:
                            hx1, hy1, hx2, hy2 = 0, 0, 0, 0

                        gestures.append({
                            "hand": handedness,
                            "gesture": gesture_name,
                            "friendly_label": friendly,
                            "confidence": round(confidence, 2),
                            "bbox": [hx1, hy1, hx2, hy2],
                            "landmarks": landmarks
                        })

                        # Draw Hand Skeleton & HUD Badge
                        if return_annotated and landmarks:
                            self._draw_hand_skeleton(annotated, raw_lm, w, h)
                            self._draw_cyber_box(
                                annotated, hx1, hy1, hx2, hy2,
                                label=f"{handedness.upper()} {friendly}",
                                color=(251, 64, 224) # Neon Magenta/Violet (B=251, G=64, R=224)
                            )
            except Exception as e:
                print(f"[VisionEngine] MediaPipe gesture error: {e}")

        # 4. Generate Natural Context Summary for IVIA's Robot Voice Brain
        summary_parts = []
        if persons:
            count = len(persons)
            summary_parts.append(f"{count} person" if count == 1 else f"{count} persons")
        if small_objects:
            obj_counts: Dict[str, int] = {}
            for o in small_objects:
                obj_counts[o['label']] = obj_counts.get(o['label'], 0) + 1
            obj_strs = [f"{c} {lbl}" if c == 1 else f"{c} {lbl}s" for lbl, c in obj_counts.items()]
            summary_parts.append(f"small objects: {', '.join(obj_strs)}")
        if gestures:
            g_strs = [f"{g['hand']} hand showing {g['friendly_label']}" for g in gestures]
            summary_parts.append(f"gestures: {', '.join(g_strs)}")

        if summary_parts:
            summary = "I currently see: " + "; ".join(summary_parts) + "."
        else:
            summary = "No persons, small objects, or hand gestures detected in front of the camera."

        # Update persistent state
        self.last_detection_time = time.time()
        self.last_detected_persons = len(persons)
        self.last_detected_objects = [o["label"] for o in small_objects]
        self.last_detected_gestures = [g["friendly_label"] for g in gestures]
        self.last_summary = summary

        # 5. Convert annotated image to base64 if requested
        annotated_b64 = None
        if return_annotated and annotated is not None:
            _, buffer = cv2.imencode('.jpg', annotated, [cv2.IMWRITE_JPEG_QUALITY, 80])
            annotated_b64 = "data:image/jpeg;base64," + base64.b64encode(buffer).decode('utf-8')

        return {
            "success": True,
            "timestamp": time.time(),
            "summary": summary,
            "person_count": len(persons),
            "persons": persons,
            "small_object_count": len(small_objects),
            "small_objects": small_objects,
            "gesture_count": len(gestures),
            "gestures": gestures,
            "annotated_frame": annotated_b64
        }

    def _draw_cyber_box(self, img, x1, y1, x2, y2, label: str, color: tuple):
        """Draws a futuristic cybernetic target frame with corner notches."""
        # Main thin frame
        cv2.rectangle(img, (x1, y1), (x2, y2), color, 1, cv2.LINE_AA)

        # Thick corner brackets
        corner_len = min(20, max(5, int((x2 - x1) * 0.2)))
        th = 3
        # Top-Left
        cv2.line(img, (x1, y1), (x1 + corner_len, y1), color, th)
        cv2.line(img, (x1, y1), (x1, y1 + corner_len), color, th)
        # Top-Right
        cv2.line(img, (x2, y1), (x2 - corner_len, y1), color, th)
        cv2.line(img, (x2, y1), (x2, y1 + corner_len), color, th)
        # Bottom-Left
        cv2.line(img, (x1, y2), (x1 + corner_len, y2), color, th)
        cv2.line(img, (x1, y2), (x1, y2 - corner_len), color, th)
        # Bottom-Right
        cv2.line(img, (x2, y2), (x2 - corner_len, y2), color, th)
        cv2.line(img, (x2, y2), (x2, y2 - corner_len), color, th)

        # Cybernetic Badge Label
        (label_w, label_h), baseline = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.45, 1)
        badge_y1 = max(0, y1 - label_h - 8)
        badge_y2 = y1
        badge_x2 = min(img.shape[1], x1 + label_w + 12)

        # Dark background backing
        cv2.rectangle(img, (x1, badge_y1), (badge_x2, badge_y2), (17, 24, 39), -1)
        # Accent border for badge
        cv2.rectangle(img, (x1, badge_y1), (badge_x2, badge_y2), color, 1)
        # Text
        cv2.putText(
            img, label, (x1 + 6, badge_y2 - 4),
            cv2.FONT_HERSHEY_SIMPLEX, 0.42, (255, 255, 255), 1, cv2.LINE_AA
        )

    def _draw_hand_skeleton(self, img, raw_landmarks, w: int, h: int):
        """Draws glowing 21-joint hand skeleton connections."""
        coords = []
        for lm in raw_landmarks:
            cx, cy = int(lm.x * w), int(lm.y * h)
            coords.append((cx, cy))

        # Draw glowing bones
        for start_idx, end_idx in HAND_CONNECTIONS:
            pt1 = coords[start_idx]
            pt2 = coords[end_idx]
            cv2.line(img, pt1, pt2, (255, 120, 240), 2, cv2.LINE_AA)

        # Draw glowing joint nodes
        for i, (cx, cy) in enumerate(coords):
            # Key joints (tips) get a larger circle
            radius = 5 if i in [4, 8, 12, 16, 20] else 3
            cv2.circle(img, (cx, cy), radius, (0, 242, 254), -1, cv2.LINE_AA)
            cv2.circle(img, (cx, cy), radius + 2, (251, 64, 224), 1, cv2.LINE_AA)

    def get_visual_context_summary(self) -> str:
        """Returns the current visual context for IVIA's cognitive conversation prompt."""
        age = time.time() - self.last_detection_time
        if age > 15.0:
            return "Vision sensor is currently idle. No active camera frame in the last 15 seconds."
        return self.last_summary
