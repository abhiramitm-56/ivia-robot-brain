# TASK 03 – Face Detection

Real-time, lightweight face detection module using OpenCV and SCRFD (InsightFace) on CPU.

---

## 📋 Features

- **Webcam Input**: Real-time stream using OpenCV VideoCapture.
- **Resolution Negotiation**: Requests target resolution `1920×1080` (1080p) with automatic fallback to `1280×720` (720p).
- **Lightweight SCRFD Detector**: Uses InsightFace with `allowed_modules=['detection']` for fast, lightweight CPU inference.
- **Multi-Face Limit**: Simultaneously detects and visualizes up to **maximum 3 faces**.
- **Facial Landmark Points**: Detects and visualizes 5 facial landmarks per face (eyes, nose, mouth corners).
- **Bounding Boxes & Confidence**: Draws clean bounding boxes and detection confidence labels for each detected face.
- **Face Size Filter**: Configurable `MIN_FACE_SIZE = 50` pixels to reject small or false positive detections.
- **Real-Time HUD**: Displays detected face count, real-time FPS, and confidence score list.
- **Benchmarking**: Calculates and prints the total frames and average detection FPS upon exit.
- **Graceful Exit & Error Handling**: Press `Q` to exit; handles camera disconnections and errors cleanly.

---

## 📁 Project Structure

```text
face_robot/
│
├── face_detection.py     # Main face detection implementation
├── requirements.txt      # Python dependencies
└── README.md             # Project documentation
```

---

## 🚀 Installation & Setup

### 1. Create and Activate Virtual Environment (Recommended)

```bash
# Using Python 3.10+
python -m venv env

# Activate on Windows
.\env\Scripts\activate
```

### 2. Install Dependencies

```bash
pip install -r requirements.txt
```

---

## ▶️ Running the Application

Run the detection script with:

```bash
python face_detection.py
```

### Controls

- **Press `Q`** on the webcam video window to safely terminate the stream and print the benchmark results.

---

## ⚙️ Configuration Parameters

You can adjust settings inside `face_detection.py`:

| Parameter | Default | Description |
| :--- | :--- | :--- |
| `MAX_FACES` | `3` | Maximum number of faces processed per frame |
| `MIN_FACE_SIZE` | `50` | Minimum bounding box width and height in pixels |
| `TARGET_WIDTH` / `TARGET_HEIGHT` | `1920`, `1080` | Preferred webcam capture resolution |
| `FALLBACK_WIDTH` / `FALLBACK_HEIGHT` | `1280`, `720` | Fallback webcam resolution |
| `DET_MODEL_NAME` | `"buffalo_l"` | InsightFace model pack (`buffalo_l` or `buffalo_sc`) |
| `DET_SIZE` | `(640, 640)` | Input dimension scale for SCRFD detector |
| `CAMERA_INDEX` | `0` | OpenCV VideoCapture camera index |

---

## 🖥️ Sample On-Screen Display (HUD)

```text
+-----------------------------------+
| Faces: 2                          |
| FPS: 28.40                        |
| Face 1 | Conf: 0.98               |
| Face 2 | Conf: 0.95               |
+-----------------------------------+
```

---

## 📊 Sample Terminal Output

```text
==================================================
  TASK 03 - Real-Time Face Detection (SCRFD)     
==================================================
Max Faces: 3 | Min Face Size: 50px | CPU Inference
Press 'Q' on the video window to quit.

[INFO] Initializing SCRFD face detector (buffalo_l) on CPU...
[INFO] Face detector initialized successfully.
[INFO] Opening camera 0...
[INFO] Camera initialized at 1920x1080 resolution.

[INFO] 'Q' pressed. Exiting...
==================================================
Total Frames Processed: 350
Total Elapsed Time    : 14.20 seconds
Average Detection FPS : 24.65 FPS
==================================================
```
