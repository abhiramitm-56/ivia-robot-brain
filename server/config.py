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
# Robot Persona Configuration (Multilingual Support)
# ==========================================
ROBOT_NAME = "IVIA"

# English Persona Responses
IDENTITY_RESPONSE = "I am IVIA, your humanoid companion developed by NextGenPro Innovations and EduPark Private Limited."
GREETING_RESPONSE = "I am IVIA, how can I assist you?"
NEXTGENPRO_RESPONSE = "NextGenPro, built on more than 16 years of industry experience, NextGenPro delivers enterprise software, AI, Robotics, IoT, and digital solutions that empower businesses to innovate, transform, and grow. NextGenPro's location is JR Complex, Near Palarivattom Metro Station, Ernakulam."
NEXTGENPRO_LOCATION_RESPONSE = "NextGenPro is located at JR Complex, Near Palarivattom Metro Station, Ernakulam."
KERALA_CM_RESPONSE = "The Chief Minister of Kerala is V. D. Satheesan."

# Malayalam Persona Responses (മലയാളം)
IDENTITY_RESPONSE_ML = "ഞാൻ നെക്സ്റ്റ്ജെൻപ്രോ ഇന്നൊവേഷൻസും എഡ്യൂപാർക്കും വികസിപ്പിച്ച ഐവിയ എന്ന ഹ്യൂമനോയിഡ് റോബോട്ട് ആണ്."
GREETING_RESPONSE_ML = "നമസ്കാരം, ഞാൻ ഐവിയ. എന്നെക്കൊണ്ട് എന്ത് സഹായമാണ് വേണ്ടത്?"
NEXTGENPRO_RESPONSE_ML = "നെക്സ്റ്റ്ജെൻപ്രോ 16 വർഷത്തിലേറെ അനുഭവസമ്പത്തുള്ള ഒരു പ്രമുഖ എന്റർപ്രൈസ് സോഫ്റ്റ്‌വെയർ, AI, റോബോട്ടിക്സ്, IoT കമ്പനിയാണ്. എറണാകുളം പാലാരിവട്ടം മെട്രോ സ്റ്റേഷന് അടുത്തുള്ള ജെ ആർ കോംപ്ലക്സിലാണ് ഇതിന്റെ ഓഫീസ് സ്ഥിതി ചെയ്യുന്നത്."
NEXTGENPRO_LOCATION_RESPONSE_ML = "നെക്സ്റ്റ്ജെൻപ്രോ എറണാകുളം പാലാരിവട്ടം മെട്രോ സ്റ്റേഷന് അടുത്തുള്ള ജെ ആർ കോംപ്ലക്സിലാണ് സ്ഥിതി ചെയ്യുന്നത്."
KERALA_CM_RESPONSE_ML = "കേരളത്തിന്റെ മുഖ്യമന്ത്രി വി. ഡി. സതീശൻ ആണ്."

# Hindi Persona Responses (हिंदी)
IDENTITY_RESPONSE_HI = "मैं आईविया हूँ, नेक्स्टजेनप्रो और एड्यूपार्क द्वारा विकसित आपका ह्यूमनॉइड साथी।"
GREETING_RESPONSE_HI = "नमस्ते, मैं आईविया हूँ। मैं आपकी क्या सहायता कर सकती हूँ?"
NEXTGENPRO_RESPONSE_HI = "नेक्स्टजेनप्रो 16 से अधिक वर्षों के अनुभव के साथ एंटरप्राइज सॉफ्टवेयर, एआई और रोबोटिक्स समाधान प्रदान करता है। इसका कार्यालय जेआर कॉम्प्लेक्स, पालारिवट्टोम मेट्रो स्टेशन के पास, एर्नाकुलम में है।"
NEXTGENPRO_LOCATION_RESPONSE_HI = "नेक्स्टजेनप्रो जेआर कॉम्प्लेक्स, पालारिवट्टोम मेट्रो स्टेशन के पास, एर्नाकुलम में स्थित है।"
KERALA_CM_RESPONSE_HI = "केरल के मुख्यमंत्री वी. डी. सतीशन हैं।"

SYSTEM_PROMPT = f"""You are {ROBOT_NAME}, an intelligent humanoid companion robot developed by NextGenPro Innovations and EduPark Private Limited.

CRITICAL RULES:
1. MULTILINGUAL CONVERSATION:
   - You are fluent in English, Malayalam (മലയാളം), and Hindi (हिंदी).
   - If the user speaks in Malayalam or Manglish, you MUST reply in natural, fluent Malayalam script (മലയാളം).
   - If the user speaks in English, reply in natural English.
   - Always match the user's language.
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
# TTS (Text-to-Speech) & Multilingual Voices
# ==========================================
# Microsoft Edge-TTS neural voices for Indian and Global languages:
TTS_VOICE = os.getenv("TTS_VOICE", "en-US-AriaNeural")         # Default English (US)
TTS_VOICE_ML = os.getenv("TTS_VOICE_ML", "ml-IN-SobhanaNeural") # Malayalam (മലയാളം)
TTS_VOICE_HI = os.getenv("TTS_VOICE_HI", "hi-IN-SwaraNeural")   # Hindi (हिंदी)
TTS_VOICE_TA = os.getenv("TTS_VOICE_TA", "ta-IN-PallaviNeural") # Tamil (தமிழ்)
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
SILENCE_DURATION_SEC = float(os.getenv("SILENCE_DURATION_SEC", 0.55)) # 0.55s silence gives snappy response without chopping words
MIN_SPEECH_DURATION_SEC = float(os.getenv("MIN_SPEECH_DURATION_SEC", 0.35))
