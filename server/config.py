import os
import sys

# Automatically discover and add workspace .venv site-packages if running from system python
workspace_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
venv_site = os.path.join(workspace_root, ".venv", "Lib", "site-packages")
if os.path.exists(venv_site) and venv_site not in sys.path:
    sys.path.insert(0, venv_site)

from dotenv import load_dotenv

load_dotenv()

# ==========================================
# Server Network Settings
# ==========================================
HOST = os.getenv("HOST", "0.0.0.0")
PORT = int(os.getenv("PORT", 8000))

# ==========================================
# Robot Persona Configuration (English Voice)
# ==========================================
ROBOT_NAME = "IVIA"

# English Persona Responses
IDENTITY_RESPONSE = "I am IVIA, your humanoid companion developed by NextGenPro Innovations and EduPark Private Limited."
GREETING_RESPONSE = "I am IVIA, how can I assist you?"
NEXTGENPRO_RESPONSE = "NextGenPro, built on more than 16 years of industry experience, delivers enterprise software, AI, Robotics, IoT, and digital solutions that empower businesses to innovate, transform, and grow. NextGenPro is located at JR Complex, Near Palarivattom Metro Station, Ernakulam."
NEXTGENPRO_LOCATION_RESPONSE = "NextGenPro is located at JR Complex, Near Palarivattom Metro Station, Ernakulam."
KERALA_CM_RESPONSE = "The Chief Minister of Kerala is V. D. Satheesan."

SYSTEM_PROMPT = f"""You are {ROBOT_NAME}, an intelligent humanoid companion robot developed by NextGenPro Innovations and EduPark Private Limited.

CRITICAL RULES:
1. ENGLISH CONVERSATION:
   - You speak strictly in natural, fluent English.
2. CONCISENESS FOR INSTANT VOICE:
   - Spoken responses MUST be strictly 1 crisp, natural sentence (maximum 15-20 words). Never output paragraphs.
3. KNOWLEDGE BASE:
   - NextGenPro: 16+ years experience, JR Complex, Near Palarivattom Metro Station, Ernakulam.
   - Kerala CM: V. D. Satheesan.
   - You have deep regional expertise on Kerala, its 14 districts, culture, and India.
4. NO FORMATTING:
   - Never use asterisks, markdown, bullet points, or emojis, as they break spoken delivery."""

# ==========================================
# AI Provider Configuration
# Supported providers: "groq", "openai", "gemini", "mock"
# ==========================================
# Groq provides ultra-fast inference (< 250ms), ideal for real-time voice bots!
AI_PROVIDER = os.getenv("AI_PROVIDER", "groq").lower()

GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")

# LLM Models
GROQ_MODEL = os.getenv("GROQ_MODEL", "qwen/qwen3.8-27b")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.0-flash")

# STT Models
GROQ_STT_MODEL = os.getenv("GROQ_STT_MODEL", "whisper-large-v3-turbo")
OPENAI_STT_MODEL = "whisper-1"

# ==========================================
# TTS (Text-to-Speech) - English Neural Voice
# ==========================================
# Microsoft Edge-TTS neural voice for English:
TTS_VOICE = os.getenv("TTS_VOICE", "en-US-AriaNeural")         # Default English (US)
TTS_RATE = os.getenv("TTS_RATE", "+12%")
TTS_VOLUME = os.getenv("TTS_VOLUME", "+0%")

# Phonetic Replacements for Natural Speech Pronunciation:
# Prevents TTS from spelling "I-V-I-A" letter by letter and corrects company names
IVIA_PHONETIC = os.getenv("IVIA_PHONETIC", "Eye-vee-ah") # or "Ee-vee-ah"
EDUPARK_PHONETIC = os.getenv("EDUPARK_PHONETIC", "Ed-you-park")
NEXTGENPRO_PHONETIC = os.getenv("NEXTGENPRO_PHONETIC", "Next-Gen-Pro")

# ==========================================
# Audio Processing Settings
# ==========================================
SAMPLE_RATE = 16000          # 16kHz
CHANNELS = 1                 # Mono
BYTES_PER_SAMPLE = 2         # 16-bit PCM (2 bytes)

# Voice Activity Detection (VAD) - Ultra-Low Latency Conversational Turn-Taking
SILENCE_THRESHOLD = int(os.getenv("SILENCE_THRESHOLD", 450))  # RMS energy threshold for speech trigger
SILENCE_DURATION_SEC = float(os.getenv("SILENCE_DURATION_SEC", 0.65)) # 0.65s silence prevents mid-sentence cutoffs while keeping response snappy
MIN_SPEECH_DURATION_SEC = float(os.getenv("MIN_SPEECH_DURATION_SEC", 0.35))
