import io
import re
from openai import OpenAI
from server.config import (
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

        # Reject transcripts with no readable words
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

        trailing_patterns = [
            r"([?.!])?\s*(?:thank\s+you|thanks)(?:\s+(?:very\s+much|so\s+much|a\s+lot|for\s+watching|for\s+listening))?[\.\!\?]*$",
            r"([?.!])?\s*(?:thanks|thank\s+you)\s+for\s+(?:watching|listening)[\.\!\?]*$",
        ]
        for pat in trailing_patterns:
            t = re.sub(pat, r"\1", t, flags=re.IGNORECASE).strip()
            t = re.sub(r",\s*$", "", t).strip()

        return t

    def transcribe(self, wav_bytes: bytes) -> tuple[str, str]:
        """
        Transcribes audio bytes into text with strict English language enforcement.
        Returns: (transcript_text, "en")
        """
        if not wav_bytes or len(wav_bytes) < 1000:
            return "", "en"

        audio_file = io.BytesIO(wav_bytes)
        audio_file.name = "audio.wav"

        whisper_context = "Hello. IVIA humanoid robot."

        # 1. Try Groq STT (Extremely fast, < 250ms) with strict English language
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
                    print(f"[STT] Human: '{cleaned}'")
                    return cleaned, "en"
                return "", "en"
            except Exception as e:
                print(f"[STT - Groq] Transcription error: {e}")

        # 2. Try OpenAI Whisper (Fallback)
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
                    print(f"[STT - OpenAI] Human: '{cleaned}'")
                    return cleaned, "en"
                return "", "en"
            except Exception as e:
                print(f"[STT - OpenAI] Transcription failed: {e}")

        return "", "en"
