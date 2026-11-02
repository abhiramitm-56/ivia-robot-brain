import re
import edge_tts
from server.audio_utils import decode_audio_to_pcm16
from server.config import (
    TTS_VOICE,
    TTS_RATE,
    TTS_VOLUME,
    SAMPLE_RATE,
    IVIA_PHONETIC,
    EDUPARK_PHONETIC,
    NEXTGENPRO_PHONETIC
)

class TTSEngine:
    def __init__(self, voice: str = TTS_VOICE):
        self.voice = voice

    def _apply_phonetic_fixes(self, text: str) -> str:
        """
        Replace names with phonetic spellings so TTS speaks them naturally
        instead of spelling out acronyms or mispronouncing portmanteaus.
        """
        # Fix IVIA (avoid spelling out I-V-I-A)
        text = re.sub(r"\bIVIA\b", IVIA_PHONETIC, text, flags=re.IGNORECASE)
        # Fix EduPark
        text = re.sub(r"\bEduPark\b", EDUPARK_PHONETIC, text, flags=re.IGNORECASE)
        text = re.sub(r"\bEdu\s*Park\b", EDUPARK_PHONETIC, text, flags=re.IGNORECASE)
        # Fix NextGenPro
        text = re.sub(r"\bNextGenPro\b", NEXTGENPRO_PHONETIC, text, flags=re.IGNORECASE)
        return text

    async def synthesize_to_pcm(self, text: str) -> bytes:
        """
        Synthesizes text into 16kHz 16-bit Mono PCM bytes using Microsoft Edge TTS.
        Runs locally without API keys and yields natural neural human voice.
        """
        if not text or not text.strip():
            return b""

        spoken_text = self._apply_phonetic_fixes(text.strip())

        try:
            communicate = edge_tts.Communicate(
                text=spoken_text,
                voice=self.voice,
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
