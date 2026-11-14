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

        # Reject transcripts with no readable words (e.g. '.', '...', '!')
        if not re.search(r"[\w\u0D00-\u0D7F\u0900-\u097F\u0B80-\u0BFF]", t):
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

    def transcribe(self, wav_bytes: bytes) -> tuple[str, str]:
        """
        Transcribes audio bytes into text and detects user language.
        Returns: (transcript_text, detected_language)
        Where detected_language is strictly 'en', 'ml', or 'hi'.
        """
        if not wav_bytes or len(wav_bytes) < 1000:
            return "", "en"

        audio_file = io.BytesIO(wav_bytes)
        audio_file.name = "audio.wav"

        whisper_context = "Hello, Namaskaram. IVIA humanoid robot."
        detected_lang = "en"
        text = ""

        # 1. Try Groq STT (Extremely fast, < 300ms)
        if self.groq_client:
            try:
                # First pass: transcribe with acoustic language detection (verbose_json)
                response = self.groq_client.audio.transcriptions.create(
                    model=GROQ_STT_MODEL,
                    file=audio_file,
                    temperature=0.0,
                    prompt=whisper_context,
                    response_format="verbose_json"
                )
                raw_lang = (getattr(response, "language", "") or "").lower()
                text = response.text.strip()

                # Determine if speech is Malayalam/Indic
                is_malayalam = (
                    raw_lang in ["malayalam", "tamil", "telugu", "kannada"]
                    or any('\u0D00' <= c <= '\u0D7F' for c in text)
                    or any(w in text.lower() for w in [
                        "namaskar", "sukham", "sugham", "perentha", "ninte", "evide",
                        "aaranu", "aaraanu", "ariyumo", "parayumo", "enthokke", "malayalam",
                        "njan", "ningal", "cheyyunne"
                    ])
                )
                is_hindi = raw_lang == "hindi" or any('\u0900' <= c <= '\u097F' for c in text)

                if is_malayalam:
                    detected_lang = "ml"
                    # If text doesn't contain native Malayalam characters yet, re-transcribe with forced language='ml'
                    if not any('\u0D00' <= c <= '\u0D7F' for c in text):
                        audio_file.seek(0)
                        r_ml = self.groq_client.audio.transcriptions.create(
                            model=GROQ_STT_MODEL,
                            file=audio_file,
                            language="ml",
                            temperature=0.0
                        )
                        text = r_ml.text.strip()
                elif is_hindi:
                    detected_lang = "hi"
                else:
                    detected_lang = "en"

                cleaned = self.clean_transcript(text)
                if cleaned:
                    print(f"[STT] Detected Lang: >> {detected_lang.upper()} << | Transcript: '{cleaned}'")
                    return cleaned, detected_lang

                # Second pass fallback if auto pass returned empty
                audio_file.seek(0)
                r_fallback = self.groq_client.audio.transcriptions.create(
                    model=GROQ_STT_MODEL,
                    file=audio_file,
                    language="ml",
                    temperature=0.0
                )
                cleaned_fb = self.clean_transcript(r_fallback.text.strip())
                if cleaned_fb:
                    print(f"[STT Fallback] Detected Lang: >> ML << | Transcript: '{cleaned_fb}'")
                    return cleaned_fb, "ml"

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
                    prompt=whisper_context
                )
                text = response.text.strip()
                cleaned = self.clean_transcript(text)
                if cleaned:
                    lang = "ml" if any('\u0D00' <= c <= '\u0D7F' for c in cleaned) else "en"
                    print(f"[STT - OpenAI] Detected Lang: >> {lang.upper()} << | Transcript: '{cleaned}'")
                    return cleaned, lang
                else:
                    return "", "en"
            except Exception as e:
                print(f"[STT - OpenAI] Transcription failed: {e}")

        # 3. Informative fallback if no API key is provided
        print("[STT] No active API key found for Groq or OpenAI.")
        return "", "en"
