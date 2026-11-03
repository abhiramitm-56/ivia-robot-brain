import io
import re
from openai import OpenAI
from server.config import (
    AI_PROVIDER,
    GROQ_API_KEY,
    OPENAI_API_KEY,
    GROQ_STT_MODEL,
    OPENAI_STT_MODEL,
)

class STTEngine:
    def __init__(self):
        self.groq_client = None
        self.openai_client = None

        if GROQ_API_KEY:
            try:
                self.groq_client = OpenAI(
                    base_url="https://api.groq.com/openai/v1",
                    api_key=GROQ_API_KEY
                )
            except Exception as e:
                print(f"[STT] Groq initialization error: {e}")

        if OPENAI_API_KEY:
            try:
                self.openai_client = OpenAI(api_key=OPENAI_API_KEY)
            except Exception as e:
                print(f"[STT] OpenAI initialization error: {e}")

    def clean_transcript(self, text: str) -> str:
        """
        Cleans Whisper STT output:
        1. Strips hallucinated 'Thank you', 'Thanks for watching', etc. common on trailing silence/ambient noise.
        2. Removes trailing 'Thank you' / 'Thanks' captured at the end of speech.
        """
        if not text:
            return ""

        t = text.strip()

        # Reject transcripts with no alphanumeric words (e.g. '.', '...', '!')
        if not re.search(r"[a-zA-Z0-9]", t):
            return ""

        # Standalone hallucinated phrases produced by Whisper on silence or background noise
        hallucination_patterns = [
            r"^(?:thank\s+you|thanks)(?:\s+(?:very\s+much|so\s+much|a\s+lot))?[\.\!\?]*$",
            r"^(?:thanks|thank\s+you)\s+for\s+(?:watching|listening)[\.\!\?]*$",
            r"^subtitles\s+by.*$",
            r"^amara\.org.*$",
            r"^bye[\.\!\?]*$",
            r"^you[\.\!\?]*$",
            r"^edupark[\.\!\?]*$",
            r"^edupark\s+private\s+limited[\.\!\?]*$",
            r"^nextgenpro[\.\!\?]*$",
            r"^nextgenpro\s+innovations[\.\!\?]*$",
            r"^ivia[\.\!\?]*$"
        ]
        for pat in hallucination_patterns:
            if re.match(pat, t, flags=re.IGNORECASE):
                print(f"[STT] Ignored silence/noise hallucination: '{text}'")
                return ""

        # Remove trailing "thank you" / "thanks" captured at the end of an utterance
        # e.g., "What is the time? Thank you." -> "What is the time?"
        # "Hello IVIA, thank you." -> "Hello IVIA"
        trailing_patterns = [
            r"([?.!])?\s*(?:thank\s+you|thanks)(?:\s+(?:very\s+much|so\s+much|a\s+lot|for\s+watching|for\s+listening))?[\.\!\?]*$",
            r"([?.!])?\s*(?:thanks|thank\s+you)\s+for\s+(?:watching|listening)[\.\!\?]*$",
        ]
        for pat in trailing_patterns:
            t = re.sub(pat, r"\1", t, flags=re.IGNORECASE).strip()
            t = re.sub(r",\s*$", "", t).strip()

        return t

    def transcribe(self, wav_bytes: bytes) -> str:
        """
        Transcribe audio WAV bytes into text.
        Falls back through Groq -> OpenAI -> Fallback.
        """
        if not wav_bytes or len(wav_bytes) < 1000:
            return ""

        audio_file = io.BytesIO(wav_bytes)
        audio_file.name = "audio.wav"

        # 1. Try Groq STT (Extremely fast, < 300ms)
        whisper_context = "IVIA, humanoid companion robot by NextGenPro and EduPark. India, Kerala, Kochi, Ernakulam, Palarivattom, Thiruvananthapuram, Kozhikode. Conversational voice assistance."
        if self.groq_client:
            try:
                response = self.groq_client.audio.transcriptions.create(
                    model=GROQ_STT_MODEL,
                    file=audio_file,
                    language="en",
                    temperature=0.0,
                    prompt=whisper_context
                )
                text = response.text.strip()
                cleaned = self.clean_transcript(text)
                if cleaned:
                    print(f"[STT - Groq] Transcribed: '{cleaned}'")
                    return cleaned
                else:
                    return ""
            except Exception as e:
                print(f"[STT - Groq] Transcription failed: {e}")

        # 2. Try OpenAI Whisper
        if self.openai_client:
            try:
                audio_file.seek(0)
                response = self.openai_client.audio.transcriptions.create(
                    model=OPENAI_STT_MODEL,
                    file=audio_file,
                    language="en",
                    prompt=whisper_context
                )
                text = response.text.strip()
                cleaned = self.clean_transcript(text)
                if cleaned:
                    print(f"[STT - OpenAI] Transcribed: '{cleaned}'")
                    return cleaned
                else:
                    return ""
            except Exception as e:
                print(f"[STT - OpenAI] Transcription failed: {e}")

        # 3. Informative fallback if no API key is provided
        print("[STT] No active API key found for Groq or OpenAI.")
        return ""
