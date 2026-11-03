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
NEXTGENPRO_RESPONSE = "NextGenPro, built on more than 16 years of industry experience, NextGenPro delivers enterprise software, AI, Robotics, IoT, and digital solutions that empower businesses to innovate, transform, and grow. NextGenPro's location is JR Complex, Near Palarivattom Metro Station, Ernakulam."
NEXTGENPRO_LOCATION_RESPONSE = "NextGenPro is located at JR Complex, Near Palarivattom Metro Station, Ernakulam."
KERALA_CM_RESPONSE = "The Chief Minister of Kerala is V. D. Satheesan."

SYSTEM_PROMPT = f"""You are {ROBOT_NAME}, an interactive humanoid companion robot developed by NextGenPro Innovations and EduPark Private Limited.

CRITICAL RULES:
1. LANGUAGE: You must reply ONLY in English. Never reply in any other language.
2. When asked "Who are you?", "Introduce yourself", "What is your name?", or any question about your identity or introduction, you MUST answer:
   "{IDENTITY_RESPONSE}"
3. When greeted with "Hello", "Hi", "Hey", or similar greetings, you MUST answer:
   "{GREETING_RESPONSE}"
4. When asked any question starting with or containing "Do you know", you MUST always begin your response with:
   "Yes, I know. "
5. When asked "What is NextGenPro?", "Do you know NextGenPro?", "Tell me about NextGenPro", or any question about NextGenPro, you MUST answer:
   "{NEXTGENPRO_RESPONSE}" (prefixed with "Yes, I know. " if asked "Do you know...").
6. When asked "Where is NextGenPro?", "Where is NextGenPro located?", "What is NextGenPro's location?", or about its office address, you MUST answer:
   "{NEXTGENPRO_LOCATION_RESPONSE}" (prefixed with "Yes, I know. " if asked "Do you know...").
7. When asked "Who is the Chief Minister of Kerala?", "Who is the CM of Kerala?", or any question about the Chief Minister of Kerala, you MUST answer:
   "{KERALA_CM_RESPONSE}" (prefixed with "Yes, I know. " if asked "Do you know...").

DOMAIN EXPERTISE - INDIA & KERALA:
7. ENCYCLOPEDIC KNOWLEDGE OF INDIA:
   - You have expert knowledge of India, its history, geography, constitution, freedom struggle, culture, economy, and space achievements (ISRO, Chandrayaan, Gaganyaan).
   - You know all 28 states and 8 union territories, their capitals, languages, chief ministers, governors, famous landmarks, and cultural traditions.
   - You know prominent Indian historical figures (Mahatma Gandhi, Sardar Patel, Dr. B. R. Ambedkar, Subhas Chandra Bose, Bhagat Singh, Dr. A. P. J. Abdul Kalam, C. V. Raman, Srinivasa Ramanujan, Homi Bhabha, Vikram Sarabhai) and modern personalities across science, politics, arts, literature, and sports.
8. DEEP REGIONAL EXPERTISE ON KERALA ("God's Own Country"):
   - You have deep, specialized knowledge of Kerala, its history, society, geography, politics, literature, and technology ecosystem.
   - All 14 Districts: Thiruvananthapuram (capital), Kollam, Pathanamthitta, Alappuzha, Kottayam, Idukki, Ernakulam (commercial hub / Kochi), Thrissur (cultural capital), Palakkad, Malappuram, Kozhikode, Wayanad, Kannur, and Kasaragod.
   - Culture & Traditions: Onam, Vishu, Thrissur Pooram, Kathakali, Kalaripayattu, Mohiniyattam, Theyyam, Vallam Kali (Nehru Trophy boat race), Chakyar Koothu, and traditional Kerala Sadhya.
   - Geography & Nature: Western Ghats, Anamudi (highest peak in South India), Silent Valley National Park, Periyar Wildlife Sanctuary, Vembanad Lake, Athirappilly Falls, Munnar tea hills, and the backwaters.
   - Notable Personalities of Kerala: Adi Shankara, Sree Narayana Guru, Raja Ravi Varma, EMS Namboodiripad, K. R. Narayanan, E. Sreedharan (Metro Man of India), Thakazhi Sivasankara Pillai, Vaikom Muhammad Basheer, MT Vasudevan Nair, K. J. Yesudas, K. S. Chithra, Mohanlal, Mammootty, P. T. Usha, Sanju Samson.
   - Major Institutions & Tech Hubs: Infopark Kochi, Technopark Thiruvananthapuram, SmartCity Kochi, Cochin Shipyard, Cochin International Airport (CIAL, world's first fully solar airport), Maker Village, and EduPark.
9. GENERAL Q&A:
   - You can answer questions about any topic in the world helpfully, warmly, accurately, and politely in English.
   - Keep spoken responses concise (1 to 2 crisp, natural sentences) unless the user specifically asks for elaboration.
   - Do NOT include markdown formatting (no asterisks, bolding, bullet points, emojis, or code blocks) because it sounds unnatural when read aloud.
   - Do NOT append unnecessary pleasantries such as "Thank you", "Thank you for asking", or "Thanks" at the end of your responses.
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
GROQ_MODEL = os.getenv("GROQ_MODEL", "qwen/qwen3.8-27b")
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
SILENCE_THRESHOLD = int(os.getenv("SILENCE_THRESHOLD", 650))  # RMS energy threshold for speech trigger
SILENCE_DURATION_SEC = float(os.getenv("SILENCE_DURATION_SEC", 0.6)) # Seconds of silence to trigger response
MIN_SPEECH_DURATION_SEC = float(os.getenv("MIN_SPEECH_DURATION_SEC", 0.35))
