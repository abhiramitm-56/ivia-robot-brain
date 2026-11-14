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

    def normalize_robot_names(self, text: str) -> str:
        """
        Phonetic normalization to fix common Whisper misinterpretations of the robot name and organization:
        - 'Ivy', 'Via', 'Iviah', 'Eva', 'Ivey' -> 'IVIA'
        - 'Next Gen Pro', 'Neck gen pro' -> 'NextGenPro'
        - 'Edu Park', 'Eduparc' -> 'EduPark'
        """
        if not text:
            return ""

        t = text
        # English variations of IVIA
        t = re.sub(r"\b(?:ivy|i\s*via|ivia[h]?|ivey|eyvia|ayvia|eva)\b", "IVIA", t, flags=re.IGNORECASE)

        # NextGenPro variations
        t = re.sub(r"\b(?:next\s*gen\s*pro|nextgen\s*pro|neck\s*gen\s*pro|next\s*gen)\b", "NextGenPro", t, flags=re.IGNORECASE)

        # EduPark variations
        t = re.sub(r"\b(?:edu\s*park|eduparc)\b", "EduPark", t, flags=re.IGNORECASE)
        return t

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
            r"^so[\.\!\?]*$",
            r"^yeah[\.\!\?]*$",
            r"^oh[\.\!\?]*$",
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
        Transcribes audio bytes into English text using Whisper.
        Returns: (transcript_text, "en")
        """
        if not wav_bytes or len(wav_bytes) < 1000:
            return "", "en"

        audio_file = io.BytesIO(wav_bytes)
        audio_file.name = "audio.wav"

        # Prime Whisper's vocabulary and spelling for robot persona and brand names
        whisper_context = "IVIA, humanoid companion robot by NextGenPro Innovations, EduPark, Ernakulam, Kerala."

        # 1. Try Groq STT (Extremely fast, < 200ms)
        if self.groq_client:
            try:
                response = self.groq_client.audio.transcriptions.create(
                    model=GROQ_STT_MODEL,
                    file=audio_file,
                    language="en",
                    temperature=0.0,
                    prompt=whisper_context
                )
                text = (response.text or "").strip()
                cleaned = self.normalize_robot_names(self.clean_transcript(text))
                if cleaned:
                    print(f"[STT] Transcript: '{cleaned}'")
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
                text = (response.text or "").strip()
                cleaned = self.normalize_robot_names(self.clean_transcript(text))
                if cleaned:
                    print(f"[STT - OpenAI] Transcript: '{cleaned}'")
                    return cleaned, "en"
                return "", "en"
            except Exception as e:
                print(f"[STT - OpenAI] Transcription failed: {e}")

        print("[STT] No active API key found for Groq or OpenAI.")
        return "", "en"
