import re
import edge_tts
from server.audio_utils import decode_audio_to_pcm16
from server.config import (
    TTS_VOICE,
    TTS_VOICE_ML,
    TTS_VOICE_HI,
    TTS_VOICE_TA,
    TTS_RATE,
    TTS_VOLUME,
    SAMPLE_RATE,
    IVIA_PHONETIC,
    EDUPARK_PHONETIC,
    NEXTGENPRO_PHONETIC
)

class TTSEngine:
    def __init__(self, default_voice: str = TTS_VOICE):
        self.default_voice = default_voice

    def detect_voice(self, text: str) -> str:
        """
        Dynamically detects language script and selects the appropriate native neural voice:
        - Malayalam (മലയാളം): ml-IN-SobhanaNeural
        - Hindi (हिंदी): hi-IN-SwaraNeural
        - Tamil (தமிழ்): ta-IN-PallaviNeural
        - English / Default: en-US-AriaNeural
        """
        if any('\u0D00' <= c <= '\u0D7F' for c in text):
            return TTS_VOICE_ML
        elif any('\u0900' <= c <= '\u097F' for c in text):
            return TTS_VOICE_HI
        elif any('\u0B80' <= c <= '\u0BFF' for c in text):
            return TTS_VOICE_TA
        return self.default_voice

    def _apply_phonetic_fixes(self, text: str) -> str:
        """
        Replace names with phonetic spellings so TTS speaks them naturally
        instead of spelling out acronyms or mispronouncing portmanteaus.
        """
        # Only apply Latin phonetic fixes if text contains Latin characters
        if re.search(r"[a-zA-Z]", text):
            text = re.sub(r"\bIVIA\b", IVIA_PHONETIC, text, flags=re.IGNORECASE)
            text = re.sub(r"\bEduPark\b", EDUPARK_PHONETIC, text, flags=re.IGNORECASE)
            text = re.sub(r"\bEdu\s*Park\b", EDUPARK_PHONETIC, text, flags=re.IGNORECASE)
            text = re.sub(r"\bNextGenPro\b", NEXTGENPRO_PHONETIC, text, flags=re.IGNORECASE)
        return text

    async def synthesize_to_pcm(self, text: str) -> bytes:
        """
        Synthesizes text into 16kHz 16-bit Mono PCM bytes using Microsoft Edge TTS.
        Dynamically uses native Malayalam, Hindi, Tamil, or English neural voices.
        """
        if not text or not text.strip():
            return b""

        spoken_text = self._apply_phonetic_fixes(text.strip())
        voice_to_use = self.detect_voice(spoken_text)

        try:
            print(f"[TTS] Synthesizing speech using voice: {voice_to_use}")
            communicate = edge_tts.Communicate(
                text=spoken_text,
                voice=voice_to_use,
                rate=TTS_RATE,
                volume=TTS_VOLUME
            )

            mp3_buffer = bytearray()
            async for chunk in communicate.stream():
                if chunk["type"] == "audio":
                    mp3_buffer.extend(chunk["data"])

            if not mp3_buffer:
                print("[TTS] Received empty audio from edge-tts.")
                return b""

            # Decode MP3 bytes into raw 16kHz 16-bit Mono PCM for ESP32 MAX98357A
            pcm_bytes = decode_audio_to_pcm16(bytes(mp3_buffer), target_sample_rate=SAMPLE_RATE)
            print(f"[TTS] Synthesized {len(pcm_bytes)} PCM bytes ({len(pcm_bytes)/(SAMPLE_RATE*2):.1f}s audio)")
            return pcm_bytes

        except Exception as e:
            print(f"[TTS] Synthesis failed: {e}")
            return b""
