import os
import cv2
import time
import csv
import numpy as np
from insightface.app import FaceAnalysis


# ============================================================
# TASK 05 - LIGHTWEIGHT FACE EMBEDDING
# ============================================================

MAX_FACES = 20
MIN_FACE_SIZE = 50

DET_CONF_THRESHOLD = 0.50


# ============================================================
# TASK 04 QUALITY SETTINGS
# ============================================================

QUALITY_THRESHOLD = 80.0
MIN_BLUR_SCORE = 35.0

MIN_BRIGHTNESS = 40.0
MAX_BRIGHTNESS = 220.0

MAX_YAW = 35.0
MAX_PITCH = 30.0


# ============================================================
# LIGHTWEIGHT CAMERA SETTINGS
# ============================================================

CAMERA_INDEX = 0

TARGET_WIDTH = 1280
TARGET_HEIGHT = 720


# ============================================================
# INSIGHTFACE SETTINGS
# ============================================================

MODEL_NAME = "buffalo_l"

# Smaller = faster CPU detection
DET_SIZE = (320, 320)


# ============================================================
# ALIGNMENT
# ============================================================

ALIGNMENT_SIZE = 112


# ============================================================
# QUALITY LOG
# ============================================================

QUALITY_LOG_FILE = "face_quality_metrics.csv"


# ============================================================
# EMBEDDING
# ============================================================

EMBEDDING_DIMENSION = 512


# ============================================================
# SIMPLE TRACKING
# ============================================================

TRACK_DISTANCE_THRESHOLD = 100
TRACK_MAX_MISSED = 10

track_cache = {}

next_track_id = 1


# ============================================================
# QUALITY WEIGHTS
# ============================================================

QUALITY_WEIGHTS = {

    "face_size": 15,
    "blur": 15,
    "brightness": 10,
    "confidence": 15,
    "yaw": 15,
    "pitch": 15,
    "occlusion": 15

}


# ============================================================
# ARC FACE 5-POINT REFERENCE
# ============================================================

ARC_FACE_DST = np.array(
    [
        [38.2946, 51.6963],
        [73.5318, 51.5014],
        [56.0252, 71.7366],
        [41.5493, 92.3655],
        [70.7299, 92.2041]
    ],
    dtype=np.float32
)


# ============================================================
# INIT INSIGHTFACE
# ============================================================

def init_face_model():

    print("=" * 65)
    print("Loading InsightFace...")
    print("=" * 65)

    models_root = os.path.join(os.path.dirname(os.path.abspath(__file__)), "models")
    os.makedirs(models_root, exist_ok=True)
    model = FaceAnalysis(
        name=MODEL_NAME,
        root=models_root,
        allowed_modules=[
            "detection",
            "recognition"
        ],
        providers=[
            "CPUExecutionProvider"
        ]
    )

    model.prepare(
        ctx_id=-1,
        det_size=DET_SIZE,
        det_thresh=DET_CONF_THRESHOLD
    )

    print("[INFO] InsightFace ready.")
    print(
        f"[INFO] Detection size: "
        f"{DET_SIZE[0]}x{DET_SIZE[1]}"
    )

    return model


# ============================================================
# CAMERA
# ============================================================

def init_camera():

    print("[INFO] Opening camera...")

    cap = cv2.VideoCapture(
        CAMERA_INDEX,
        cv2.CAP_DSHOW
    )

    if not cap.isOpened():

        print("[WARN] DirectShow failed.")

        cap = cv2.VideoCapture(
            CAMERA_INDEX
        )

    if not cap.isOpened():

        raise RuntimeError(
            "Could not open webcam."
        )

    cap.set(
        cv2.CAP_PROP_FRAME_WIDTH,
        TARGET_WIDTH
    )

    cap.set(
        cv2.CAP_PROP_FRAME_HEIGHT,
        TARGET_HEIGHT
    )

    # Reduce camera buffer
    cap.set(
        cv2.CAP_PROP_BUFFERSIZE,
        1
    )

    width = int(
        cap.get(
            cv2.CAP_PROP_FRAME_WIDTH
        )
    )

    height = int(
        cap.get(
            cv2.CAP_PROP_FRAME_HEIGHT
        )
    )

    print(
        f"[INFO] Camera: "
        f"{width}x{height}"
    )

    return cap


# ============================================================
# BLUR
# ============================================================

def calculate_blur_score(face_crop):

    if face_crop.size == 0:
        return 0.0

    gray = cv2.cvtColor(
        face_crop,
        cv2.COLOR_BGR2GRAY
    )

    score = cv2.Laplacian(
        gray,
        cv2.CV_64F
    ).var()

    return float(score)


# ============================================================
# BRIGHTNESS
# ============================================================

def calculate_brightness(face_crop):

    if face_crop.size == 0:
        return 0.0

    gray = cv2.cvtColor(
        face_crop,
        cv2.COLOR_BGR2GRAY
    )

    return float(
        np.mean(gray)
    )


# ============================================================
# POSE
# ============================================================

def estimate_pose(landmarks):

    if landmarks.shape != (5, 2):

        return None, None

    left_eye = landmarks[0]
    right_eye = landmarks[1]
    nose = landmarks[2]

    left_mouth = landmarks[3]
    right_mouth = landmarks[4]

    eye_center = (
        left_eye +
        right_eye
    ) / 2.0

    mouth_center = (
        left_mouth +
        right_mouth
    ) / 2.0

    eye_distance = np.linalg.norm(
        right_eye -
        left_eye
    )

    if eye_distance < 1:

        return None, None

    # YAW
    horizontal_offset = (
        nose[0] -
        eye_center[0]
    )

    yaw_ratio = (
        horizontal_offset /
        eye_distance
    )

    yaw = yaw_ratio * 70.0

    # PITCH
    eye_to_mouth = (
        mouth_center[1] -
        eye_center[1]
    )

    if abs(eye_to_mouth) < 1:

        return float(yaw), None

    nose_position = (
        nose[1] -
        eye_center[1]
    )

    expected_position = (
        eye_to_mouth * 0.55
    )

    difference = (
        nose_position -
        expected_position
    )

    pitch_ratio = (
        difference /
        eye_to_mouth
    )

    pitch = pitch_ratio * 60.0

    return (
        float(yaw),
        float(pitch)
    )


# ============================================================
# OCCLUSION
# ============================================================

def check_occlusion(
    face_crop,
    landmarks,
    bbox_width,
    bbox_height
):

    if face_crop.size == 0:

        return True, "empty_face"

    if landmarks.shape != (5, 2):

        return True, "invalid_landmarks"

    if not np.isfinite(landmarks).all():

        return True, "invalid_landmarks"

    if (
        bbox_width <= 0
        or
        bbox_height <= 0
    ):

        return True, "invalid_bbox"

    min_x, min_y = np.min(
        landmarks,
        axis=0
    )

    max_x, max_y = np.max(
        landmarks,
        axis=0
    )

    landmark_width = (
        max_x - min_x
    )

    landmark_height = (
        max_y - min_y
    )

    if landmark_width < (
        bbox_width * 0.20
    ):

        return True, "unstable_landmarks"

    if landmark_height < (
        bbox_height * 0.15
    ):

        return True, "unstable_landmarks"

    return False, "not_detected"


# ============================================================
# ALIGNMENT
# ============================================================

def align_face(
    frame,
    landmarks,
    output_size=112
):

    if landmarks.shape != (5, 2):

        return None

    destination = ARC_FACE_DST.copy()

    if output_size != 112:

        scale = (
            output_size /
            112.0
        )

        destination *= scale

    source = landmarks.astype(
        np.float32
    )

    transform, _ = cv2.estimateAffinePartial2D(
        source,
        destination,
        method=cv2.LMEDS
    )

    if transform is None:

        return None

    aligned = cv2.warpAffine(
        frame,
        transform,
        (
            output_size,
            output_size
        ),
        borderMode=cv2.BORDER_CONSTANT,
        borderValue=(0, 0, 0)
    )

    return aligned


# ============================================================
# FACE DETECTION
# ============================================================

def detect_faces(
    model,
    frame
):

    raw_faces = model.get(frame)

    valid_faces = []

    for face in raw_faces:

        x1, y1, x2, y2 = (
            face.bbox.astype(int)
        )

        width = x2 - x1
        height = y2 - y1

        if (
            width < MIN_FACE_SIZE
            or
            height < MIN_FACE_SIZE
        ):

            continue

        confidence = float(
            face.det_score
        )

        if confidence < DET_CONF_THRESHOLD:

            continue

        if face.kps is None:

            continue

        landmarks = face.kps.astype(
            np.float32
        )

        if landmarks.shape != (5, 2):

            continue

        valid_faces.append({

            "bbox": [
                x1,
                y1,
                x2,
                y2
            ],

            "confidence":
                confidence,

            "landmarks":
                landmarks.tolist(),

            "width":
                width,

            "height":
                height
        })

    valid_faces.sort(
        key=lambda x:
        x["confidence"],
        reverse=True
    )

    return valid_faces[:MAX_FACES]


# ============================================================
# QUALITY EVALUATION
# ============================================================

def evaluate_face_quality(
    frame,
    face
):

    x1, y1, x2, y2 = (
        face["bbox"]
    )

    frame_h, frame_w = (
        frame.shape[:2]
    )

    x1 = max(
        0,
        min(
            x1,
            frame_w - 1
        )
    )

    y1 = max(
        0,
        min(
            y1,
            frame_h - 1
        )
    )

    x2 = max(
        x1 + 1,
        min(
            x2,
            frame_w
        )
    )

    y2 = max(
        y1 + 1,
        min(
            y2,
            frame_h
        )
    )

    face_crop = frame[
        y1:y2,
        x1:x2
    ]

    face_width = x2 - x1
    face_height = y2 - y1

    landmarks = np.array(
        face["landmarks"],
        dtype=np.float32
    )

    confidence = float(
        face["confidence"]
    )

    blur_score = calculate_blur_score(
        face_crop
    )

    brightness = calculate_brightness(
        face_crop
    )

    yaw, pitch = estimate_pose(
        landmarks
    )

    occluded, occlusion_reason = (
        check_occlusion(
            face_crop,
            landmarks,
            face_width,
            face_height
        )
    )

    checks = {

        "face_size":
            (
                face_width >= MIN_FACE_SIZE
                and
                face_height >= MIN_FACE_SIZE
            ),

        "blur":
            blur_score >= MIN_BLUR_SCORE,

        "brightness":
            (
                MIN_BRIGHTNESS
                <= brightness
                <= MAX_BRIGHTNESS
            ),

        "confidence":
            confidence >= DET_CONF_THRESHOLD,

        "yaw":
            (
                yaw is not None
                and
                abs(yaw) <= MAX_YAW
            ),

        "pitch":
            (
                pitch is not None
                and
                abs(pitch) <= MAX_PITCH
            ),

        "occlusion":
            not occluded
    }

    quality_score = 0.0

    for name, passed in checks.items():

        if passed:

            quality_score += (
                QUALITY_WEIGHTS[name]
            )

    # FINAL RULE
    blur_ok = (
        blur_score >= MIN_BLUR_SCORE
    )

    quality_ok = (
        blur_ok
        and
        quality_score >= QUALITY_THRESHOLD
    )

    rejection_reasons = []

    for name, passed in checks.items():

        if not passed:

            rejection_reasons.append(
                name
            )

    if quality_ok:

        rejection_reason = "OK"

    elif not blur_ok:

        rejection_reason = "BLUR_REJECT"

    elif quality_score < QUALITY_THRESHOLD:

        rejection_reason = (
            "QUALITY_BELOW_80"
        )

    elif rejection_reasons:

        rejection_reason = ", ".join(
            rejection_reasons
        )

    else:

        rejection_reason = (
            "QUALITY_REJECT"
        )

    metrics = {

        "face_width":
            face_width,

        "face_height":
            face_height,

        "blur_score":
            blur_score,

        "brightness":
            brightness,

        "yaw":
            yaw,

        "pitch":
            pitch,

        "occluded":
            occluded,

        "occlusion_reason":
            occlusion_reason,

        "confidence":
            confidence,

        "quality_score":
            quality_score,

        "quality":
            (
                "ACCEPT"
                if quality_ok
                else
                "REJECT"
            ),

        "rejection_reason":
            rejection_reason
    }

    return quality_ok, metrics


# ============================================================
# TRACK CENTER
# ============================================================

def get_face_center(face):

    x1, y1, x2, y2 = (
        face["bbox"]
    )

    return np.array(
        [
            (x1 + x2) / 2.0,
            (y1 + y2) / 2.0
        ],
        dtype=np.float32
    )


# ============================================================
# TRACK ID
# ============================================================

def assign_track_id(face):

    global next_track_id

    center = get_face_center(
        face
    )

    best_id = None
    best_distance = float(
        "inf"
    )

    for track_id, data in track_cache.items():

        distance = np.linalg.norm(
            center -
            data["center"]
        )

        if (
            distance <
            best_distance
            and
            distance <
            TRACK_DISTANCE_THRESHOLD
        ):

            best_distance = distance
            best_id = track_id

    if best_id is not None:

        track_cache[
            best_id
        ]["center"] = center

        track_cache[
            best_id
        ]["missed"] = 0

        return best_id

    track_id = next_track_id

    next_track_id += 1

    track_cache[track_id] = {

        "center":
            center,

        "embedding":
            None,

        "missed":
            0
    }

    return track_id


# ============================================================
# TRACK CLEANUP
# ============================================================

def update_track_misses(
    active_ids
):

    remove_ids = []

    for track_id in list(
        track_cache.keys()
    ):

        if track_id not in active_ids:

            track_cache[
                track_id
            ]["missed"] += 1

        else:

            track_cache[
                track_id
            ]["missed"] = 0

        if (
            track_cache[
                track_id
            ]["missed"]
            >
            TRACK_MAX_MISSED
        ):

            remove_ids.append(
                track_id
            )

    for track_id in remove_ids:

        del track_cache[
            track_id
        ]


# ============================================================
# NORMALIZE EMBEDDING
# ============================================================

def normalize_embedding(
    embedding
):

    embedding = np.asarray(
        embedding,
        dtype=np.float32
    ).reshape(-1)

    norm = np.linalg.norm(
        embedding
    )

    if norm == 0:

        return None

    return (
        embedding /
        norm
    )


# ============================================================
# GENERATE EMBEDDING
# ============================================================

def generate_embedding(
    model,
    aligned_face
):

    if aligned_face is None:

        return None

    try:

        recognition_model = (
            model.models["recognition"]
        )

        embedding = (
            recognition_model.get_feat(
                aligned_face
            )
        )

        embedding = np.asarray(
            embedding,
            dtype=np.float32
        ).reshape(-1)

        embedding = normalize_embedding(
            embedding
        )

        return embedding

    except Exception as e:

        print(
            "[ERROR] Embedding error:",
            e
        )

        return None


# ============================================================
# CACHE EMBEDDING
# ============================================================

def get_or_create_embedding(
    model,
    aligned_face,
    track_id
):

    # CACHE HIT
    if (
        track_id in track_cache
        and
        track_cache[
            track_id
        ]["embedding"] is not None
    ):

        return (
            track_cache[
                track_id
            ]["embedding"],
            True
        )

    # CACHE MISS
    embedding = generate_embedding(
        model,
        aligned_face
    )

    if embedding is None:

        return None, False

    track_cache[
        track_id
    ]["embedding"] = embedding

    return embedding, False


# ============================================================
# CSV
# ============================================================

def init_quality_log(
    filename
):

    headers = [

        "timestamp",
        "face_width",
        "face_height",
        "blur_score",
        "brightness",
        "yaw",
        "pitch",
        "occluded",
        "occlusion_reason",
        "confidence",
        "quality_score",
        "quality",
        "rejection_reason"
    ]

    with open(
        filename,
        "w",
        newline="",
        encoding="utf-8"
    ) as file:

        writer = csv.DictWriter(
            file,
            fieldnames=headers
        )

        writer.writeheader()


def log_quality_metrics(
    filename,
    metrics
):

    row = {

        "timestamp":
            time.strftime(
                "%Y-%m-%d %H:%M:%S"
            ),

        "face_width":
            metrics["face_width"],

        "face_height":
            metrics["face_height"],

        "blur_score":
            f'{metrics["blur_score"]:.2f}',

        "brightness":
            f'{metrics["brightness"]:.2f}',

        "yaw":
            (
                ""
                if metrics["yaw"] is None
                else
                f'{metrics["yaw"]:.2f}'
            ),

        "pitch":
            (
                ""
                if metrics["pitch"] is None
                else
                f'{metrics["pitch"]:.2f}'
            ),

        "occluded":
            metrics["occluded"],

        "occlusion_reason":
            metrics["occlusion_reason"],

        "confidence":
            f'{metrics["confidence"]:.3f}',

        "quality_score":
            f'{metrics["quality_score"]:.1f}',

        "quality":
            metrics["quality"],

        "rejection_reason":
            metrics["rejection_reason"]
    }

    with open(
        filename,
        "a",
        newline="",
        encoding="utf-8"
    ) as file:

        writer = csv.DictWriter(
            file,
            fieldnames=row.keys()
        )

        writer.writerow(row)


# ============================================================
# DRAW FACE
# ============================================================

def draw_face_result(
    frame,
    face,
    metrics
):

    x1, y1, x2, y2 = (
        face["bbox"]
    )

    quality = metrics[
        "quality"
    ]

    if quality == "ACCEPT":

        box_color = (
            0,
            255,
            0
        )

    else:

        box_color = (
            0,
            0,
            255
        )

    cv2.rectangle(
        frame,
        (x1, y1),
        (x2, y2),
        box_color,
        2
    )

    # Landmarks
    for point in face[
        "landmarks"
    ]:

        px, py = map(
            int,
            point
        )

        cv2.circle(
            frame,
            (px, py),
            3,
            (255, 255, 0),
            -1
        )

    yaw = metrics["yaw"]
    pitch = metrics["pitch"]

    yaw_text = (
        "N/A"
        if yaw is None
        else
        f"{yaw:.1f}"
    )

    pitch_text = (
        "N/A"
        if pitch is None
        else
        f"{pitch:.1f}"
    )

    lines = [

        f"ID: "
        f"{face.get('track_id', '-')}",

        f"Quality: "
        f"{metrics['quality_score']:.0f}% "
        f"{quality}",

        f"Conf: "
        f"{metrics['confidence']:.2f}",

        f"Blur: "
        f"{metrics['blur_score']:.0f}",

        f"Bright: "
        f"{metrics['brightness']:.0f}",

        f"Yaw: {yaw_text}",

        f"Pitch: {pitch_text}",

        f"Emb: "
        f"{face.get('embedding_status', '-')}"
    ]

    if quality == "REJECT":

        lines.append(
            "Reason: "
            +
            metrics[
                "rejection_reason"
            ]
        )

    start_y = y2 + 18

    for i, text in enumerate(lines):

        y = (
            start_y +
            i * 17
        )

        if y >= frame.shape[0]:

            break

        cv2.putText(
            frame,
            text,
            (x1, y),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.45,
            box_color,
            1,
            cv2.LINE_AA
        )

    cv2.putText(
        frame,
        f"{quality} "
        f"{metrics['quality_score']:.0f}%",
        (
            x1,
            max(
                20,
                y1 - 8
            )
        ),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.55,
        box_color,
        2,
        cv2.LINE_AA
    )


# ============================================================
# PANEL
# ============================================================

def draw_panel(
    frame,
    fps,
    accepted,
    rejected,
    new_embeddings,
    cached_embeddings
):

    overlay = frame.copy()

    cv2.rectangle(
        overlay,
        (10, 10),
        (430, 170),
        (20, 20, 20),
        -1
    )

    cv2.addWeighted(
        overlay,
        0.70,
        frame,
        0.30,
        0,
        frame
    )

    lines = [

        f"FPS: {fps:.2f}",

        f"Accepted: {accepted}",

        f"Rejected: {rejected}",

        f"New Embeddings: "
        f"{new_embeddings}",

        f"Cached: "
        f"{cached_embeddings}",

        "Quality >= 80%",

        "Blur >= 35",

        "Q = Quit"
    ]

    for i, text in enumerate(
        lines
    ):

        cv2.putText(
            frame,
            text,
            (
                20,
                32 + i * 19
            ),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.52,
            (255, 255, 255),
            1,
            cv2.LINE_AA
        )


# ============================================================
# MAIN
# ============================================================

def main():

    print("=" * 65)
    print("TASK 05 - LIGHTWEIGHT FACE EMBEDDING")
    print("=" * 65)

    print(
        "Camera: 1280x720"
    )

    print(
        "Detection: 320x320"
    )

    print(
        "Maximum faces: 10"
    )

    print(
        "Quality: >= 80%"
    )

    print(
        "Blur: >= 35"
    )

    print(
        "Embedding: ArcFace"
    )

    print(
        "Normalization: L2"
    )

    print(
        "Cache: ENABLED"
    )

    print("=" * 65)

    # --------------------------------------------------------
    # Model
    # --------------------------------------------------------

    try:

        model = init_face_model()

    except Exception as e:

        print(
            "[FATAL] Model failed:"
        )

        print(e)

        return

    # --------------------------------------------------------
    # Camera
    # --------------------------------------------------------

    try:

        cap = init_camera()

    except Exception as e:

        print(
            "[FATAL] Camera failed:"
        )

        print(e)

        return

    # --------------------------------------------------------
    # CSV
    # --------------------------------------------------------

    init_quality_log(
        QUALITY_LOG_FILE
    )

    # --------------------------------------------------------
    # FPS
    # --------------------------------------------------------

    frame_count = 0

    start_time = time.time()

    previous_time = (
        start_time
    )

    current_fps = 0.0

    total_new = 0
    total_cached = 0

    window_name = (
        "TASK 05 - "
        "Lightweight Face Embedding"
    )

    cv2.namedWindow(
        window_name,
        cv2.WINDOW_NORMAL
    )

    try:

        while True:

            # =================================================
            # CAMERA
            # =================================================

            ret, frame = cap.read()

            if (
                not ret
                or
                frame is None
            ):

                continue

            frame_count += 1

            # =================================================
            # FPS
            # =================================================

            now = time.time()

            dt = (
                now -
                previous_time
            )

            previous_time = now

            if dt > 0:

                instant_fps = (
                    1.0 /
                    dt
                )

                if current_fps == 0:

                    current_fps = (
                        instant_fps
                    )

                else:

                    current_fps = (
                        0.9 *
                        current_fps
                        +
                        0.1 *
                        instant_fps
                    )

            # =================================================
            # DETECTION
            # =================================================

            faces = detect_faces(
                model,
                frame
            )

            accepted_count = 0
            rejected_count = 0

            new_count = 0
            cached_count = 0

            active_ids = []

            # =================================================
            # EACH FACE
            # =================================================

            for face in faces:

                # ---------------------------------------------
                # TRACK ID
                # ---------------------------------------------

                track_id = assign_track_id(
                    face
                )

                face[
                    "track_id"
                ] = track_id

                active_ids.append(
                    track_id
                )

                # ---------------------------------------------
                # QUALITY
                # ---------------------------------------------

                quality_ok, metrics = (
                    evaluate_face_quality(
                        frame,
                        face
                    )
                )

                log_quality_metrics(
                    QUALITY_LOG_FILE,
                    metrics
                )

                # ---------------------------------------------
                # ACCEPTED
                # ---------------------------------------------

                if quality_ok:

                    accepted_count += 1

                    # -----------------------------------------
                    # ALIGN
                    # -----------------------------------------

                    landmarks = np.array(
                        face["landmarks"],
                        dtype=np.float32
                    )

                    aligned_face = align_face(
                        frame,
                        landmarks,
                        ALIGNMENT_SIZE
                    )

                    if aligned_face is None:

                        accepted_count -= 1
                        rejected_count += 1

                        face[
                            "embedding_status"
                        ] = "ALIGN_FAIL"

                    else:

                        # -------------------------------------
                        # TASK 05 EMBEDDING
                        # -------------------------------------

                        embedding, cached = (
                            get_or_create_embedding(
                                model,
                                aligned_face,
                                track_id
                            )
                        )

                        if embedding is not None:

                            face[
                                "embedding"
                            ] = embedding

                            face[
                                "embedding_dimension"
                            ] = len(
                                embedding
                            )

                            if cached:

                                face[
                                    "embedding_status"
                                ] = "CACHED"

                                cached_count += 1
                                total_cached += 1

                            else:

                                face[
                                    "embedding_status"
                                ] = "NEW"

                                new_count += 1
                                total_new += 1

                        else:

                            accepted_count -= 1
                            rejected_count += 1

                            face[
                                "embedding_status"
                            ] = "EMB_FAIL"

                # ---------------------------------------------
                # REJECTED
                # ---------------------------------------------

                else:

                    rejected_count += 1

                    face[
                        "embedding_status"
                    ] = "NOT_GENERATED"

                # ---------------------------------------------
                # DRAW
                # ---------------------------------------------

                draw_face_result(
                    frame,
                    face,
                    metrics
                )

            # =================================================
            # CLEAN OLD TRACKS
            # =================================================

            update_track_misses(
                active_ids
            )

            # =================================================
            # PANEL
            # =================================================

            draw_panel(
                frame,
                current_fps,
                accepted_count,
                rejected_count,
                new_count,
                cached_count
            )

            # =================================================
            # DISPLAY
            # =================================================

            cv2.imshow(
                window_name,
                frame
            )

            key = (
                cv2.waitKey(1)
                & 0xFF
            )

            if (
                key == ord("q")
                or
                key == ord("Q")
            ):

                break

    except KeyboardInterrupt:

        print(
            "[INFO] Stopped."
        )

    except Exception as e:

        print(
            "[ERROR]",
            e
        )

    finally:

        cap.release()

        cv2.destroyAllWindows()

        total_time = (
            time.time()
            -
            start_time
        )

        if total_time > 0:

            average_fps = (
                frame_count /
                total_time
            )

        else:

            average_fps = 0

        print("=" * 65)

        print("TASK 05 SUMMARY")

        print("=" * 65)

        print(
            f"Frames: "
            f"{frame_count}"
        )

        print(
            f"Average FPS: "
            f"{average_fps:.2f}"
        )

        print(
            f"New embeddings: "
            f"{total_new}"
        )

        print(
            f"Cached embeddings: "
            f"{total_cached}"
        )

        print(
            f"Active tracks: "
            f"{len(track_cache)}"
        )

        print(
            f"Embedding dimension: "
            f"{EMBEDDING_DIMENSION}"
        )

        print(
            "Normalization: L2"
        )

        print(
            "Detection size: "
            f"{DET_SIZE}"
        )

        print("=" * 65)


# ============================================================
# RUN
# ============================================================

if __name__ == "__main__":

    main()