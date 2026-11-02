import os
import cv2
import time
import sqlite3
import pickle
import numpy as np

from insightface.app import FaceAnalysis


# ============================================================
# SETTINGS
# ============================================================

MODEL_NAME = "buffalo_l"

CAMERA_INDEX = 0

DET_SIZE = (320, 320)

CAMERA_WIDTH = 1280
CAMERA_HEIGHT = 720

MIN_FACE_SIZE = 50
DET_CONF_THRESHOLD = 0.50

QUALITY_THRESHOLD = 80.0
MIN_BLUR_SCORE = 35.0

MIN_BRIGHTNESS = 40.0
MAX_BRIGHTNESS = 220.0

MAX_YAW = 35.0
MAX_PITCH = 30.0

ALIGNMENT_SIZE = 112

# ------------------------------------------------------------
# CAPTURE TIME = 6 SECONDS
# ------------------------------------------------------------

CAPTURE_SECONDS = 6

MIN_SELECTED_FRAMES = 5
MAX_SELECTED_FRAMES = 10

DATABASE_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "face_database.db")


# ============================================================
# ARC FACE LANDMARKS
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
# DATABASE
# ============================================================

def init_database():

    conn = sqlite3.connect(DATABASE_FILE)

    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS persons (

            person_id TEXT PRIMARY KEY,

            name TEXT NOT NULL,

            metadata TEXT,

            created_at TEXT,

            updated_at TEXT
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS embeddings (

            id INTEGER PRIMARY KEY AUTOINCREMENT,

            person_id TEXT,

            embedding BLOB,

            embedding_index INTEGER,

            FOREIGN KEY(person_id)
            REFERENCES persons(person_id)
        )
    """)

    conn.commit()

    conn.close()

    print("[INFO] Database ready.")


# ============================================================
# MODEL
# ============================================================

def load_model():

    print("[INFO] Loading InsightFace...")

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

    print("[INFO] Model loaded.")

    return model


# ============================================================
# CAMERA
# ============================================================

def open_camera():

    cap = cv2.VideoCapture(
        CAMERA_INDEX,
        cv2.CAP_DSHOW
    )

    if not cap.isOpened():

        cap = cv2.VideoCapture(
            CAMERA_INDEX
        )

    if not cap.isOpened():

        raise RuntimeError(
            "Camera could not be opened."
        )

    cap.set(
        cv2.CAP_PROP_FRAME_WIDTH,
        CAMERA_WIDTH
    )

    cap.set(
        cv2.CAP_PROP_FRAME_HEIGHT,
        CAMERA_HEIGHT
    )

    cap.set(
        cv2.CAP_PROP_BUFFERSIZE,
        1
    )

    print("[INFO] Camera opened.")

    return cap


# ============================================================
# BLUR
# ============================================================

def calculate_blur(face_crop):

    if face_crop.size == 0:

        return 0.0

    gray = cv2.cvtColor(
        face_crop,
        cv2.COLOR_BGR2GRAY
    )

    return float(
        cv2.Laplacian(
            gray,
            cv2.CV_64F
        ).var()
    )


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
    ) / 2

    mouth_center = (
        left_mouth +
        right_mouth
    ) / 2

    eye_distance = np.linalg.norm(
        right_eye -
        left_eye
    )

    if eye_distance < 1:

        return None, None

    # --------------------------------------------------------
    # YAW
    # --------------------------------------------------------

    horizontal_offset = (
        nose[0] -
        eye_center[0]
    )

    yaw_ratio = (
        horizontal_offset /
        eye_distance
    )

    yaw = yaw_ratio * 70

    # --------------------------------------------------------
    # PITCH
    # --------------------------------------------------------

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

    pitch = pitch_ratio * 60

    return (
        float(yaw),
        float(pitch)
    )


# ============================================================
# DETECT BEST FACE
# ============================================================

def detect_best_face(
    model,
    frame
):

    faces = model.get(frame)

    valid_faces = []

    for face in faces:

        x1, y1, x2, y2 = (
            face.bbox.astype(int)
        )

        width = x2 - x1
        height = y2 - y1

        confidence = float(
            face.det_score
        )

        if width < MIN_FACE_SIZE:
            continue

        if height < MIN_FACE_SIZE:
            continue

        if confidence < DET_CONF_THRESHOLD:
            continue

        if face.kps is None:
            continue

        landmarks = face.kps.astype(
            np.float32
        )

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
                landmarks
        })

    if not valid_faces:

        return None

    # Highest confidence face

    valid_faces.sort(
        key=lambda x:
        x["confidence"],
        reverse=True
    )

    return valid_faces[0]


# ============================================================
# QUALITY CHECK
# ============================================================

def check_quality(
    frame,
    face
):

    x1, y1, x2, y2 = (
        face["bbox"]
    )

    h, w = frame.shape[:2]

    x1 = max(
        0,
        min(x1, w - 1)
    )

    y1 = max(
        0,
        min(y1, h - 1)
    )

    x2 = max(
        x1 + 1,
        min(x2, w)
    )

    y2 = max(
        y1 + 1,
        min(y2, h)
    )

    crop = frame[
        y1:y2,
        x1:x2
    ]

    width = x2 - x1
    height = y2 - y1

    landmarks = face[
        "landmarks"
    ]

    confidence = face[
        "confidence"
    ]

    blur = calculate_blur(
        crop
    )

    brightness = calculate_brightness(
        crop
    )

    yaw, pitch = estimate_pose(
        landmarks
    )

    # --------------------------------------------------------
    # CHECKS
    # --------------------------------------------------------

    face_size_ok = (
        width >= MIN_FACE_SIZE
        and
        height >= MIN_FACE_SIZE
    )

    blur_ok = (
        blur >= MIN_BLUR_SCORE
    )

    brightness_ok = (
        MIN_BRIGHTNESS
        <= brightness
        <= MAX_BRIGHTNESS
    )

    confidence_ok = (
        confidence >=
        DET_CONF_THRESHOLD
    )

    yaw_ok = (
        yaw is not None
        and
        abs(yaw) <= MAX_YAW
    )

    pitch_ok = (
        pitch is not None
        and
        abs(pitch) <= MAX_PITCH
    )

    # --------------------------------------------------------
    # QUALITY SCORE
    # --------------------------------------------------------

    score = 0

    if face_size_ok:
        score += 15

    if blur_ok:
        score += 15

    if brightness_ok:
        score += 10

    if confidence_ok:
        score += 15

    if yaw_ok:
        score += 15

    if pitch_ok:
        score += 15

    # Landmark validity

    if (
        landmarks.shape ==
        (5, 2)
    ):

        score += 15

    # --------------------------------------------------------
    # FINAL DECISION
    # --------------------------------------------------------

    accepted = (
        blur_ok
        and
        score >= QUALITY_THRESHOLD
    )

    return accepted, {

        "score": score,

        "blur": blur,

        "brightness":
            brightness,

        "confidence":
            confidence,

        "yaw":
            yaw,

        "pitch":
            pitch
    }


# ============================================================
# ALIGN FACE
# ============================================================

def align_face(
    frame,
    landmarks
):

    source = landmarks.astype(
        np.float32
    )

    transform, _ = (
        cv2.estimateAffinePartial2D(
            source,
            ARC_FACE_DST,
            method=cv2.LMEDS
        )
    )

    if transform is None:

        return None

    aligned = cv2.warpAffine(
        frame,
        transform,
        (
            ALIGNMENT_SIZE,
            ALIGNMENT_SIZE
        ),
        borderMode=cv2.BORDER_CONSTANT,
        borderValue=(0, 0, 0)
    )

    return aligned


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
            "[ERROR] Embedding:",
            e
        )

        return None


# ============================================================
# SELECT BEST FRAMES
# ============================================================

def select_best_frames(
    candidates
):

    candidates.sort(
        key=lambda x:
        x["quality_score"],
        reverse=True
    )

    selected = candidates[
        :MAX_SELECTED_FRAMES
    ]

    return selected


# ============================================================
# SAVE PERSON
# ============================================================

def save_person(
    person_id,
    name,
    metadata,
    embeddings
):

    conn = sqlite3.connect(
        DATABASE_FILE
    )

    cursor = conn.cursor()

    current_time = time.strftime(
        "%Y-%m-%d %H:%M:%S"
    )

    # --------------------------------------------------------
    # PERSON
    # --------------------------------------------------------

    cursor.execute("""
        INSERT OR REPLACE INTO persons
        (
            person_id,
            name,
            metadata,
            created_at,
            updated_at
        )
        VALUES (?, ?, ?, ?, ?)
    """, (
        person_id,
        name,
        metadata,
        current_time,
        current_time
    ))

    # --------------------------------------------------------
    # DELETE OLD EMBEDDINGS
    # --------------------------------------------------------

    cursor.execute("""
        DELETE FROM embeddings
        WHERE person_id = ?
    """, (
        person_id,
    ))

    # --------------------------------------------------------
    # SAVE NEW EMBEDDINGS
    # --------------------------------------------------------

    for index, embedding in enumerate(
        embeddings
    ):

        embedding_blob = sqlite3.Binary(
            pickle.dumps(
                embedding
            )
        )

        cursor.execute("""
            INSERT INTO embeddings
            (
                person_id,
                embedding,
                embedding_index
            )
            VALUES (?, ?, ?)
        """, (
            person_id,
            embedding_blob,
            index
        ))

    conn.commit()

    conn.close()

    print(
        f"[INFO] Saved {person_id}"
    )

    print(
        f"[INFO] Embeddings: "
        f"{len(embeddings)}"
    )


# ============================================================
# CHECK EXISTING PERSON
# ============================================================

def person_exists(
    person_id
):

    conn = sqlite3.connect(
        DATABASE_FILE
    )

    cursor = conn.cursor()

    cursor.execute("""
        SELECT person_id
        FROM persons
        WHERE person_id = ?
    """, (
        person_id,
    ))

    result = cursor.fetchone()

    conn.close()

    return result is not None


# ============================================================
# ENROLLMENT
# ============================================================

def enroll_person(
    model,
    person_id,
    name,
    metadata
):

    print("=" * 60)

    print(
        f"Enrollment started:"
        f" {name}"
    )

    print(
        f"Person ID: {person_id}"
    )

    print(
        f"Capture time:"
        f" {CAPTURE_SECONDS} seconds"
    )

    print("=" * 60)

    cap = open_camera()

    candidates = []

    start_time = time.time()

    while True:

        ret, frame = cap.read()

        if not ret:

            continue

        elapsed = (
            time.time()
            -
            start_time
        )

        remaining = (
            CAPTURE_SECONDS
            -
            elapsed
        )

        # ----------------------------------------------------
        # 6 SECONDS COMPLETED
        # ----------------------------------------------------

        if remaining <= 0:

            break

        face = detect_best_face(
            model,
            frame
        )

        status = (
            "SEARCHING FOR FACE..."
        )

        if face is not None:

            accepted, quality = (
                check_quality(
                    frame,
                    face
                )
            )

            x1, y1, x2, y2 = (
                face["bbox"]
            )

            if accepted:

                status = (
                    f"GOOD FRAME "
                    f"{quality['score']:.0f}%"
                )

                # --------------------------------------------
                # ALIGN
                # --------------------------------------------

                aligned = align_face(
                    frame,
                    face["landmarks"]
                )

                if aligned is not None:

                    candidates.append({

                        "frame":
                            frame.copy(),

                        "aligned":
                            aligned.copy(),

                        "quality_score":
                            quality["score"],

                        "blur":
                            quality["blur"],

                        "brightness":
                            quality[
                                "brightness"
                            ]
                    })

            else:

                status = (
                    f"REJECT "
                    f"{quality['score']:.0f}%"
                )

            # ------------------------------------------------
            # DRAW FACE BOX
            # ------------------------------------------------

            cv2.rectangle(
                frame,
                (x1, y1),
                (x2, y2),
                (
                    0,
                    255,
                    0
                )
                if accepted
                else
                (
                    0,
                    0,
                    255
                ),
                2
            )

            # ------------------------------------------------
            # QUALITY INFO
            # ------------------------------------------------

            cv2.putText(
                frame,
                f"Quality: "
                f"{quality['score']:.0f}%",
                (x1, y1 - 35),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.55,
                (
                    0,
                    255,
                    0
                )
                if accepted
                else
                (
                    0,
                    0,
                    255
                ),
                2
            )

            cv2.putText(
                frame,
                f"Blur: "
                f"{quality['blur']:.0f}",
                (x1, y1 - 10),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.55,
                (255, 255, 0),
                2
            )

        # ----------------------------------------------------
        # DISPLAY TIMER
        # ----------------------------------------------------

        cv2.putText(
            frame,
            f"Capturing: "
            f"{remaining:.1f}s",
            (20, 35),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.8,
            (255, 255, 255),
            2
        )

        cv2.putText(
            frame,
            status,
            (20, 70),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.65,
            (0, 255, 255),
            2
        )

        cv2.putText(
            frame,
            f"Good frames: "
            f"{len(candidates)}",
            (20, 105),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.65,
            (0, 255, 255),
            2
        )

        cv2.putText(
            frame,
            "Keep your face "
            "inside the camera",
            (20, 140),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.55,
            (255, 255, 255),
            1
        )

        cv2.putText(
            frame,
            "Press Q to cancel",
            (20, 175),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.55,
            (255, 255, 255),
            1
        )

        cv2.imshow(
            "TASK 06 - Enrollment",
            frame
        )

        key = (
            cv2.waitKey(1)
            &
            0xFF
        )

        if key == ord("q"):

            cap.release()

            cv2.destroyAllWindows()

            print(
                "[INFO] Enrollment cancelled."
            )

            return False

    # ========================================================
    # CLOSE CAMERA AFTER 6 SECONDS
    # ========================================================

    cap.release()

    cv2.destroyAllWindows()

    # ========================================================
    # SELECT BEST 5-10
    # ========================================================

    print(
        f"[INFO] Good frames:"
        f" {len(candidates)}"
    )

    if len(candidates) < MIN_SELECTED_FRAMES:

        print(
            "[ERROR] Not enough "
            "high-quality frames."
        )

        print(
            f"Need at least "
            f"{MIN_SELECTED_FRAMES}"
        )

        return False

    selected = select_best_frames(
        candidates
    )

    print(
        f"[INFO] Selected:"
        f" {len(selected)} frames"
    )

    # ========================================================
    # GENERATE EMBEDDINGS
    # ========================================================

    embeddings = []

    for index, item in enumerate(
        selected,
        start=1
    ):

        print(
            f"[INFO] Embedding "
            f"{index}/"
            f"{len(selected)}"
        )

        embedding = generate_embedding(
            model,
            item["aligned"]
        )

        if embedding is not None:

            embeddings.append(
                embedding
            )

            print(
                f"       Dimension:"
                f" {len(embedding)}"
            )

        else:

            print(
                "       Failed"
            )

    # ========================================================
    # VALIDATE
    # ========================================================

    if len(embeddings) < MIN_SELECTED_FRAMES:

        print(
            "[ERROR] Not enough "
            "valid embeddings."
        )

        return False

    # ========================================================
    # SAVE
    # ========================================================

    save_person(
        person_id,
        name,
        metadata,
        embeddings
    )

    print("=" * 60)

    print(
        "ENROLLMENT SUCCESS"
    )

    print(
        f"Person ID: {person_id}"
    )

    print(
        f"Name: {name}"
    )

    print(
        f"Embeddings saved:"
        f" {len(embeddings)}"
    )

    print("=" * 60)

    return True


# ============================================================
# MAIN
# ============================================================

def main():

    print("=" * 60)

    print(
        "TASK 06 - FACE ENROLLMENT"
    )

    print("=" * 60)

    # --------------------------------------------------------
    # DATABASE
    # --------------------------------------------------------

    init_database()

    # --------------------------------------------------------
    # MODEL
    # --------------------------------------------------------

    model = load_model()

    # --------------------------------------------------------
    # USER INPUT
    # --------------------------------------------------------

    person_id = input(
        "Enter Person ID: "
    ).strip()

    if not person_id:

        print(
            "[ERROR] Person ID required."
        )

        return

    name = input(
        "Enter Name: "
    ).strip()

    if not name:

        print(
            "[ERROR] Name required."
        )

        return

    metadata = input(
        "Enter Metadata "
        "(optional): "
    ).strip()

    # --------------------------------------------------------
    # RE-ENROLLMENT
    # --------------------------------------------------------

    if person_exists(
        person_id
    ):

        print(
            f"[INFO] {person_id} "
            f"already exists."
        )

        choice = input(
            "Re-enroll/update? "
            "(y/n): "
        ).strip().lower()

        if choice != "y":

            print(
                "Enrollment cancelled."
            )

            return

        print(
            "[INFO] Existing "
            "embeddings will be "
            "replaced."
        )

    # --------------------------------------------------------
    # ENROLL
    # --------------------------------------------------------

    enroll_person(
        model,
        person_id,
        name,
        metadata
    )


# ============================================================
# RUN
# ============================================================

if __name__ == "__main__":

    main()