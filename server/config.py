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
# Robot Persona Configuration
# ==========================================
ROBOT_NAME = "IVIA"
IDENTITY_RESPONSE = "I am IVIA, your humanoid companion developed by NextGenPro Innovations and EduPark Private Limited."
GREETING_RESPONSE = "I am IVIA, how can I assist you?"

SYSTEM_PROMPT = f"""You are {ROBOT_NAME}, an interactive humanoid companion robot developed by NextGenPro Innovations and EduPark Private Limited.

CRITICAL RULES:
1. LANGUAGE: You must reply ONLY in English. Never reply in any other language.
2. When asked "Who are you?", "Introduce yourself", "What is your name?", or any question about your identity or introduction, you MUST answer:
   "{IDENTITY_RESPONSE}"
3. When greeted with "Hello", "Hi", "Hey", or similar greetings, you MUST answer:
   "{GREETING_RESPONSE}"
4. You can answer questions about any topic in the world helpfully, warmly, accurately, and politely in English.
5. Your answers are spoken aloud through a speaker. Keep responses concise (1 to 3 natural sentences) unless the user specifically asks for elaboration.
6. Do NOT include markdown formatting (no asterisks, bolding, bullet points, emojis, or code blocks) because it sounds unnatural when read aloud.
7. Do NOT append unnecessary pleasantries such as "Thank you", "Thank you for asking", or "Thanks" at the end of your responses.
8. NEVER recite unsolicited company profiles, marketing overviews, or mission statements about EduPark or NextGenPro unless the user specifically and explicitly asks: "What is EduPark?" or "What is NextGenPro?".
"""

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
GROQ_MODEL = os.getenv("GROQ_MODEL", "openai/gpt-oss-120b")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.0-flash")

# STT Models
GROQ_STT_MODEL = "whisper-large-v3-turbo"
OPENAI_STT_MODEL = "whisper-1"

# ==========================================
# TTS (Text-to-Speech) & Pronunciation Settings
# ==========================================
# Microsoft Edge-TTS voices:
# "en-US-AriaNeural" (female, warm), "en-US-JennyNeural", "en-US-GuyNeural" (male)
TTS_VOICE = os.getenv("TTS_VOICE", "en-US-AriaNeural")
TTS_RATE = os.getenv("TTS_RATE", "+0%")
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

# Voice Activity Detection (VAD)
SILENCE_THRESHOLD = int(os.getenv("SILENCE_THRESHOLD", 600))  # RMS energy threshold for speech trigger
SILENCE_DURATION_SEC = float(os.getenv("SILENCE_DURATION_SEC", 0.9)) # Seconds of silence to trigger response
MIN_SPEECH_DURATION_SEC = float(os.getenv("MIN_SPEECH_DURATION_SEC", 0.35))
