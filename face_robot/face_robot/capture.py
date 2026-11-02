# =============================================================================
# MULTI-PERSON FACE RECOGNITION + INDIVIDUAL VOICE GREETING
# =============================================================================

import os
import sys
import argparse
import requests
import cv2
import sqlite3
import pickle
import numpy as np
import time
import threading
import queue
import warnings
import pyttsx3

from insightface.app import FaceAnalysis

# Suppress noisy warnings
warnings.filterwarnings("ignore", category=FutureWarning)
os.environ["TF_ENABLE_ONEDNN_OPTS"] = "0"

# =============================================================================
# CONFIG
# =============================================================================

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DATABASE_FILE = os.path.join(SCRIPT_DIR, "face_database.db")

# Similarity threshold for matching registered faces
SIMILARITY_THRESHOLD = 0.35

# Number of consecutive frames required to confirm presence before speaking
CONFIRMATION_FRAMES = 3

# Person must be absent for this long (in seconds) before greeting again
ABSENCE_RESET_SECONDS = 2.0

# Maximum distance in pixels between consecutive frames to match an unknown track
TRACK_DISTANCE_THRESHOLD = 120

CAMERA_INDEX = 0
CAMERA_WIDTH = 1280
CAMERA_HEIGHT = 720

# 640x640 detection size enables reliable detection of multiple simultaneous faces
DET_SIZE = (640, 640)
DET_CONF_THRESHOLD = 0.45
MAX_FACES = 10

TTS_RATE = 130
TTS_VOLUME = 1.0


warnings.filterwarnings("ignore", category=FutureWarning)


# =============================================================================
# TTS QUEUE & WORKER
# =============================================================================

speech_queue = queue.Queue()


def tts_worker():
    """
    Dedicated background worker thread that speaks queued messages sequentially without overlap.
    Re-initializes the pyttsx3 SAPI5 engine per message to prevent Windows COM deadlocks
    and ensure that every queued person's greeting actually produces audio output.
    """
    print("[TTS] Speech worker ready.")

    while True:
        text = speech_queue.get()
        try:
            # Sentinel None stops the worker
            if text is None:
                print("[TTS] Worker stopped.")
                break

            print(f"[TTS PLAYING] {text}")

            # Re-initialize engine per utterance to avoid SAPI5 event-loop freeze on Windows
            try:
                engine = pyttsx3.init()
                engine.setProperty("rate", TTS_RATE)
                engine.setProperty("volume", TTS_VOLUME)
                engine.say(text)
                engine.runAndWait()
                engine.stop()
                del engine
            except Exception as e:
                print(f"[TTS ERROR] Speech synthesis failed: {e}")

            print(f"[TTS FINISHED] {text}")

        except Exception as e:
            print(f"[TTS ERROR] {e}")

        finally:
            speech_queue.task_done()


# Start dedicated TTS worker daemon thread
tts_thread = threading.Thread(target=tts_worker, daemon=True)
tts_thread.start()


def speak_name(name):
    """Queues a greeting for a registered person."""
    text = f"Hello {name}"
    print(f"[VOICE QUEUED] {text}")
    speech_queue.put(text)


def speak_unknown():
    """Queues an announcement for an unknown person."""
    text = "Unknown person"
    print(f"[VOICE QUEUED] {text}")
    speech_queue.put(text)


# =============================================================================
# LOAD DATABASE
# =============================================================================

def load_gallery(db_path=DATABASE_FILE):
    """Loads all registered persons and their ArcFace embeddings from SQLite."""
    print("\n" + "=" * 50)
    print("[INFO] Loading face database")
    print("=" * 50)

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # Load persons table
    cursor.execute("SELECT person_id, name FROM persons")
    persons = cursor.fetchall()
    person_names = {str(pid): str(name) for pid, name in persons}

    # Load embeddings table
    cursor.execute(
        """
        SELECT person_id, embedding
        FROM embeddings
        ORDER BY person_id, embedding_index
        """
    )
    rows = cursor.fetchall()
    conn.close()

    gallery_embeddings = []
    gallery_pids = []

    for person_id, blob in rows:
        try:
            emb = pickle.loads(blob)
            emb = np.asarray(emb, dtype=np.float32).reshape(-1)
            norm = np.linalg.norm(emb)
            if norm == 0:
                continue
            emb = emb / norm
            gallery_embeddings.append(emb)
            gallery_pids.append(str(person_id))
        except Exception as e:
            print(f"[WARN] Embedding load failed ID={person_id}: {e}")

    if len(gallery_embeddings) > 0:
        gallery_matrix = np.vstack(gallery_embeddings)
    else:
        gallery_matrix = np.empty((0, 512), dtype=np.float32)

    print(f"[INFO] Registered persons: {len(person_names)}")
    for pid, name in person_names.items():
        print(f"   ID={pid} | NAME={name}")

    print(f"[INFO] Total embeddings: {len(gallery_pids)}")

    return person_names, gallery_matrix, gallery_pids


# =============================================================================
# MATCHING LOGIC
# =============================================================================

def get_all_scores(live_embedding, gallery_matrix, gallery_pids):
    """Calculates cosine similarity of live_embedding against all gallery embeddings."""
    if live_embedding is None or gallery_matrix.shape[0] == 0:
        return []

    live_embedding = np.asarray(live_embedding, dtype=np.float32).reshape(-1)
    norm = np.linalg.norm(live_embedding)
    if norm == 0:
        return []

    live_embedding = live_embedding / norm
    similarities = np.dot(gallery_matrix, live_embedding)

    results = [
        (float(similarity), str(gallery_pids[i]))
        for i, similarity in enumerate(similarities)
    ]
    results.sort(key=lambda x: x[0], reverse=True)
    return results


def match_multiple_faces(faces, gallery_matrix, gallery_pids, person_names):
    """
    Independently matches all faces in the current frame against registered embeddings.
    Assigns the highest-similarity candidate pairs first so that:
    - Each face gets its best matching registered person.
    - No two faces are simultaneously assigned to the same registered person.
    - Faces below SIMILARITY_THRESHOLD are classified as UNKNOWN.
    """
    all_candidates = []

    for face_index, face in enumerate(faces):
        scores = get_all_scores(face.embedding, gallery_matrix, gallery_pids)
        for similarity, pid in scores:
            if similarity >= SIMILARITY_THRESHOLD:
                all_candidates.append((similarity, face_index, pid))

    # Highest similarity score first
    all_candidates.sort(key=lambda x: x[0], reverse=True)

    assigned_faces = set()
    assigned_people = set()
    results = {}

    for similarity, face_index, pid in all_candidates:
        if face_index in assigned_faces or pid in assigned_people:
            continue

        assigned_faces.add(face_index)
        assigned_people.add(pid)
        results[face_index] = (
            True,
            pid,
            person_names.get(pid, "Unknown"),
            similarity
        )

    # Remaining faces are treated as UNKNOWN
    for face_index, face in enumerate(faces):
        if face_index in results:
            continue

        scores = get_all_scores(face.embedding, gallery_matrix, gallery_pids)
        best_similarity = scores[0][0] if scores else 0.0

        results[face_index] = (
            False,
            None,
            None,
            best_similarity
        )

    return results


# =============================================================================
# VISUALIZATION
# =============================================================================

def draw_face(frame, bbox, is_known, person_id, name, similarity):
    """
    Draws face bounding box, name/UNKNOWN status, similarity score,
    and person ID on the video frame.
    """
    x1, y1, x2, y2 = bbox
    h, w = frame.shape[:2]

    x1 = max(0, x1)
    y1 = max(0, y1)
    x2 = min(w - 1, x2)
    y2 = min(h - 1, y2)

    if is_known:
        color = (0, 255, 0)
        label = f"{name} {similarity:.2f}"
    else:
        color = (0, 0, 255)
        label = f"UNKNOWN {similarity:.2f}"

    # Bounding box
    cv2.rectangle(frame, (x1, y1), (x2, y2), color, 2)

    font = cv2.FONT_HERSHEY_SIMPLEX
    font_scale = 0.65
    thickness = 2

    (text_width, text_height), _ = cv2.getTextSize(
        label, font, font_scale, thickness
    )

    label_y1 = max(55, y1 - text_height - 10)
    label_y2 = label_y1 + text_height + 10

    # Background for label
    cv2.rectangle(
        frame,
        (x1, label_y1),
        (x1 + text_width + 10, label_y2),
        (20, 20, 20),
        -1
    )

    # Label text (Name/UNKNOWN + similarity score)
    cv2.putText(
        frame,
        label,
        (x1 + 5, label_y2 - 5),
        font,
        font_scale,
        color,
        thickness,
        cv2.LINE_AA
    )

    # Person ID for registered persons
    if is_known and person_id is not None:
        id_text = f"ID: {person_id}"
        cv2.putText(
            frame,
            id_text,
            (x1, min(h - 10, y2 + 22)),
            font,
            0.55,
            (0, 255, 0),
            2,
            cv2.LINE_AA
        )


def draw_hud(frame, fps, registered, detected):
    """Draws top information banner."""
    h, w = frame.shape[:2]

    cv2.rectangle(frame, (0, 0), (w, 48), (20, 20, 20), -1)

    cv2.putText(
        frame,
        f"FPS: {fps:.1f}",
        (15, 31),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.65,
        (0, 255, 200),
        2,
        cv2.LINE_AA
    )

    cv2.putText(
        frame,
        f"Registered: {registered}",
        (150, 31),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.65,
        (255, 255, 255),
        2,
        cv2.LINE_AA
    )

    cv2.putText(
        frame,
        f"Faces: {detected}",
        (390, 31),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.65,
        (255, 200, 0),
        2,
        cv2.LINE_AA
    )

    cv2.putText(
        frame,
        f"Threshold: {SIMILARITY_THRESHOLD:.2f}",
        (510, 31),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.60,
        (220, 220, 220),
        2,
        cv2.LINE_AA
    )

    cv2.putText(
        frame,
        "Q = EXIT",
        (w - 110, 31),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.55,
        (180, 180, 180),
        2,
        cv2.LINE_AA
    )


# =============================================================================
# ESP32-S3 DIRECT FRAME GRABBER (BYPASSES FFMPEG 30s TIMEOUT)
# =============================================================================

class ESP32CamReader:
    """Zero-timeout frame grabber for ESP32-S3 OV3660 with retries."""
    def __init__(self, ip):
        self.url = f"http://{ip}/capture"
        self.session = requests.Session()
        self.last_err = ""

    def read(self, timeout=2.5):
        try:
            resp = self.session.get(self.url, timeout=timeout)
            if resp.status_code == 200:
                arr = np.frombuffer(resp.content, dtype=np.uint8)
                img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
                if img is not None:
                    return True, img
            else:
                self.last_err = f"HTTP {resp.status_code}"
        except Exception as e:
            self.last_err = str(e)
        return False, None

    def isOpened(self):
        return True

    def release(self):
        pass


# =============================================================================
# MAIN
# =============================================================================

def main():
    parser = argparse.ArgumentParser(description="Multi-Person Face Recognition with ESP32-S3 Cam")
    parser.add_argument("--ip", default="10.35.199.118", help="ESP32-S3 IP Address (e.g. 10.35.199.118)")
    parser.add_argument("--url", default="", help="Direct stream/snapshot URL")
    parser.add_argument("--webcam", action="store_true", help="Force using local PC webcam")
    args = parser.parse_args()

    print("\n" + "=" * 58)
    print(" MULTI-PERSON FACE RECOGNITION + VOICE SYSTEM (ESP32-S3)")
    print("=" * 58)

    # -------------------------------------------------------------------------
    # LOAD DATABASE
    # -------------------------------------------------------------------------
    person_names, gallery_matrix, gallery_pids = load_gallery(DATABASE_FILE)

    if len(person_names) == 0:
        print("[ERROR] No registered persons in database.")
        return

    if gallery_matrix.shape[0] == 0:
        print("[ERROR] No face embeddings found in database.")
        return

    # -------------------------------------------------------------------------
    # LOAD INSIGHTFACE
    # -------------------------------------------------------------------------
    print("\n[INFO] Loading InsightFace model...")
    models_root = os.path.join(SCRIPT_DIR, "models")
    os.makedirs(models_root, exist_ok=True)
    model = FaceAnalysis(
        name="buffalo_l",
        root=models_root,
        allowed_modules=["detection", "recognition"],
        providers=["CPUExecutionProvider"]
    )
    model.prepare(ctx_id=-1, det_size=DET_SIZE, det_thresh=DET_CONF_THRESHOLD)
    print(f"[INFO] InsightFace ready (Detection size: {DET_SIZE[0]}x{DET_SIZE[1]}).")

    # -------------------------------------------------------------------------
    # CAMERA (ESP32-S3 or Local Webcam)
    # -------------------------------------------------------------------------
    is_esp32 = False
    target_ip = args.ip.strip()
    if "://" in target_ip:
        target_ip = target_ip.split("://")[1]
    target_ip = target_ip.split("/")[0]

    if args.webcam:
        print(f"[INFO] Using local PC webcam (index {CAMERA_INDEX})...")
        cap = cv2.VideoCapture(CAMERA_INDEX, cv2.CAP_DSHOW)
        if not cap.isOpened():
            cap = cv2.VideoCapture(CAMERA_INDEX)
    else:
        print(f"[INFO] Connecting to ESP32-S3 camera at: http://{target_ip}/capture")
        cap = ESP32CamReader(target_ip)
        is_esp32 = True

        # Attempt initial frame with retries
        ret = False
        print("[INFO] Waiting for first frame from ESP32...")
        for attempt in range(1, 4):
            ret, test_frame = cap.read(timeout=3.0)
            if ret:
                break
            print(f"  Attempt {attempt}/3 failed ({cap.last_err}). Retrying...")
            time.sleep(1.0)

        if not ret:
            print(f"[WARN] ESP32 at {target_ip} not responding ({cap.last_err}). Falling back to local PC webcam...")
            cap = cv2.VideoCapture(CAMERA_INDEX)
            is_esp32 = False
        else:
            print("[SUCCESS] Connected to ESP32-S3 camera feed!")

    if cap is not None and not is_esp32:
        try:
            cap.set(cv2.CAP_PROP_FRAME_WIDTH, CAMERA_WIDTH)
            cap.set(cv2.CAP_PROP_FRAME_HEIGHT, CAMERA_HEIGHT)
            cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
        except Exception:
            pass

    print("[INFO] Camera initialized successfully.")
    print("[INFO] Multi-person recognition running. Press 'Q' to quit, 'F' to flip.")

    # -------------------------------------------------------------------------
    # INDEPENDENT TRACKING STATE: REGISTERED PERSONS
    # -------------------------------------------------------------------------
    person_state = {
        str(pid): {
            "consecutive_frames": 0,
            "last_seen": 0.0,
            "greeted": False
        }
        for pid in person_names.keys()
    }

    # -------------------------------------------------------------------------
    # INDEPENDENT TRACKING STATE: UNKNOWN PERSONS (SPATIAL CENTROID TRACKING)
    # -------------------------------------------------------------------------
    unknown_tracks = {}
    next_unknown_id = 1

    # -------------------------------------------------------------------------
    # FPS
    # -------------------------------------------------------------------------
    fps = 0.0
    previous_time = time.perf_counter()
    flip_frame = False

    # -------------------------------------------------------------------------
    # CAMERA LOOP
    # -------------------------------------------------------------------------
    try:
        while True:
            ret, frame = cap.read()

            if not ret or frame is None:
                canvas = np.zeros((480, 640, 3), dtype=np.uint8)
                cv2.putText(canvas, "CONNECTING TO CAMERA...", (100, 220), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 200, 255), 2)
                cv2.putText(canvas, f"Target: http://{target_ip}/capture" if is_esp32 else "Webcam", (100, 260), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (180, 180, 180), 1)
                cv2.imshow("Multi Person Face Recognition", canvas)
                key = cv2.waitKey(100) & 0xFF
                if key in (ord("q"), ord("Q"), 27):
                    break
                continue

            if flip_frame:
                frame = cv2.flip(frame, 1)

            current_time = time.perf_counter()
            dt = current_time - previous_time
            previous_time = current_time

            if dt > 0:
                current_fps = 1.0 / dt
                fps = fps * 0.9 + current_fps * 0.1

            # -----------------------------------------------------------------
            # DETECT ALL FACES IN CURRENT FRAME
            # -----------------------------------------------------------------
            try:
                faces = model.get(frame)
            except Exception as e:
                print(f"[ERROR] Face detection exception: {e}")
                faces = []

            faces = faces[:MAX_FACES]

            # -----------------------------------------------------------------
            # 1-TO-1 MATCHING FOR ALL DETECTED FACES
            # -----------------------------------------------------------------
            matches = match_multiple_faces(
                faces,
                gallery_matrix,
                gallery_pids,
                person_names
            )

            current_frame_known_pids = set()
            current_registered_detections = []
            current_unknown_detections = []

            # -----------------------------------------------------------------
            # PROCESS DETECTIONS & LOG RESULTS
            # -----------------------------------------------------------------
            for face_index, face in enumerate(faces):
                bbox = face.bbox.astype(int)
                center = np.array(
                    [(bbox[0] + bbox[2]) / 2.0, (bbox[1] + bbox[3]) / 2.0],
                    dtype=np.float32
                )
                (
                    is_known,
                    person_id,
                    name,
                    similarity
                ) = matches[face_index]

                if is_known and person_id is not None:
                    person_id = str(person_id)
                    current_frame_known_pids.add(person_id)
                    current_registered_detections.append({
                        "face_index": face_index,
                        "person_id": person_id,
                        "name": name,
                        "center": center,
                        "bbox": bbox,
                        "similarity": similarity
                    })
                    print(f"[DETECTED] {name} | ID={person_id} | Similarity={similarity:.2f}")
                else:
                    print(f"[UNKNOWN] Similarity={similarity:.2f}")
                    current_unknown_detections.append({
                        "face_index": face_index,
                        "bbox": bbox,
                        "center": center,
                        "similarity": similarity
                    })

                # Draw on frame
                draw_face(frame, bbox, is_known, person_id, name, similarity)

            # -----------------------------------------------------------------
            # 1. INDEPENDENT TRACKING & VOICE: REGISTERED PERSONS
            # -----------------------------------------------------------------
            for pid, state in person_state.items():
                name = person_names.get(pid, f"Person {pid}")

                if pid in current_frame_known_pids:
                    state["last_seen"] = current_time
                    state["consecutive_frames"] += 1

                    # Confirm presence after consecutive frames
                    if state["consecutive_frames"] >= CONFIRMATION_FRAMES:
                        if not state["greeted"]:
                            state["greeted"] = True
                            print(f"[CONFIRMED] {name} | ID={pid}")
                            speak_name(name)

                else:
                    # Reset consecutive frame counter when absent in this frame
                    state["consecutive_frames"] = 0

                    # Reset greeted status only after full absence duration
                    if state["last_seen"] > 0:
                        absent_time = current_time - state["last_seen"]
                        if absent_time > ABSENCE_RESET_SECONDS:
                            if state["greeted"]:
                                print(f"[LEFT] {name}")
                            state["greeted"] = False
                            state["last_seen"] = 0.0

            # -----------------------------------------------------------------
            # 2. INDEPENDENT TRACKING & VOICE: UNKNOWN PERSONS
            # -----------------------------------------------------------------
            # Discard any unknown track that is close to a newly recognized registered person
            for reg_face in current_registered_detections:
                k_center = reg_face["center"]
                for trk_id in list(unknown_tracks.keys()):
                    if np.linalg.norm(k_center - unknown_tracks[trk_id]["center"]) < TRACK_DISTANCE_THRESHOLD:
                        del unknown_tracks[trk_id]

            # Match current unknown detections to active unknown tracks
            matched_track_ids = set()
            matched_det_indices = set()

            if unknown_tracks and current_unknown_detections:
                det_candidates = []
                for trk_id, trk in unknown_tracks.items():
                    for d_idx, det in enumerate(current_unknown_detections):
                        dist = np.linalg.norm(trk["center"] - det["center"])
                        if dist < TRACK_DISTANCE_THRESHOLD:
                            det_candidates.append((dist, trk_id, d_idx))

                # Nearest distance match first
                det_candidates.sort(key=lambda x: x[0])

                for dist, trk_id, d_idx in det_candidates:
                    if trk_id in matched_track_ids or d_idx in matched_det_indices:
                        continue

                    matched_track_ids.add(trk_id)
                    matched_det_indices.add(d_idx)

                    # Update existing unknown track
                    det = current_unknown_detections[d_idx]
                    trk = unknown_tracks[trk_id]
                    trk["center"] = det["center"]
                    trk["bbox"] = det["bbox"]
                    trk["similarity"] = det["similarity"]
                    trk["last_seen"] = current_time
                    trk["consecutive_frames"] += 1

                    # Confirm unknown person after consecutive frames
                    if trk["consecutive_frames"] >= CONFIRMATION_FRAMES:
                        if not trk["greeted"]:
                            trk["greeted"] = True
                            print("[CONFIRMED] UNKNOWN")
                            speak_unknown()

            # Create new tracks for unmatched unknown detections
            for d_idx, det in enumerate(current_unknown_detections):
                if d_idx not in matched_det_indices:
                    trk_id = next_unknown_id
                    next_unknown_id += 1

                    unknown_tracks[trk_id] = {
                        "track_id": trk_id,
                        "center": det["center"],
                        "bbox": det["bbox"],
                        "similarity": det["similarity"],
                        "last_seen": current_time,
                        "consecutive_frames": 1,
                        "greeted": False
                    }

                    if CONFIRMATION_FRAMES == 1:
                        unknown_tracks[trk_id]["greeted"] = True
                        print("[CONFIRMED] UNKNOWN")
                        speak_unknown()

            # Clean up unknown tracks absent for > ABSENCE_RESET_SECONDS
            for trk_id in list(unknown_tracks.keys()):
                if trk_id not in matched_track_ids:
                    unknown_tracks[trk_id]["consecutive_frames"] = 0
                    absent_time = current_time - unknown_tracks[trk_id]["last_seen"]
                    if absent_time > ABSENCE_RESET_SECONDS:
                        if unknown_tracks[trk_id]["greeted"]:
                            print(f"[LEFT] UNKNOWN")
                        del unknown_tracks[trk_id]

            # -----------------------------------------------------------------
            # HUD & DISPLAY
            # -----------------------------------------------------------------
            draw_hud(frame, fps, len(person_names), len(faces))

            cv2.imshow("Multi Person Face Recognition", frame)

            key = cv2.waitKey(1) & 0xFF
            if key in (ord("q"), ord("Q"), 27):
                break
            elif key in (ord("f"), ord("F")):
                flip_frame = not flip_frame
                print(f"[INFO] Flip frame: {flip_frame}")

    except KeyboardInterrupt:
        print("[INFO] Interrupted by user.")

    except Exception as e:
        print(f"[ERROR] Unexpected runtime error: {e}")

    finally:
        # ---------------------------------------------------------------------
        # CLEANUP
        # ---------------------------------------------------------------------
        if cap is not None:
            cap.release()
        cv2.destroyAllWindows()

        # Stop background TTS worker
        speech_queue.put(None)
        tts_thread.join(timeout=2.0)

        print("[INFO] Program stopped.")


# =============================================================================
# RUN
# =============================================================================

if __name__ == "__main__":
    main()