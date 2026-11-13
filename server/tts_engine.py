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
        self._cache = {}

    async def warm_cache(self):
        """
        Pre-warm high-frequency persona responses into RAM on startup.
        Ensures greetings, identity, and location questions play back in 0ms!
        """
        from server.config import (
            IDENTITY_RESPONSE, IDENTITY_RESPONSE_ML,
            GREETING_RESPONSE, GREETING_RESPONSE_ML,
            NEXTGENPRO_LOCATION_RESPONSE, NEXTGENPRO_LOCATION_RESPONSE_ML
        )
        prewarm_texts = [
            GREETING_RESPONSE,
            GREETING_RESPONSE_ML,
            IDENTITY_RESPONSE,
            IDENTITY_RESPONSE_ML,
            NEXTGENPRO_LOCATION_RESPONSE,
            NEXTGENPRO_LOCATION_RESPONSE_ML,
            "Yes, I know.",
            "അതെ, എനിക്കറിയാം."
        ]
        for t in prewarm_texts:
            try:
                await self.synthesize_to_pcm(t)
            except Exception:
                pass
        print(f"[TTS Engine] Pre-warmed {len(self._cache)} core responses into memory for 0ms instant playback!")

    def detect_voice(self, text: str) -> str:
        """
        Detects language script and strictly selects the appropriate native neural voice:
        - Malayalam (മലയാളം): ml-IN-SobhanaNeural
        - English: en-US-AriaNeural
        """
        if any('\u0D00' <= c <= '\u0D7F' for c in text):
            return TTS_VOICE_ML
        return self.default_voice

    def _apply_phonetic_fixes(self, text: str) -> str:
        """
        Replace names with phonetic spellings so TTS speaks them naturally
        instead of spelling out acronyms or mispronouncing portmanteaus.
        """
        # Only apply Latin phonetic fixes if text contains Latin characters
        if re.search(r"[a-zA-Z]", text):
            # If text is primarily Malayalam, use native Malayalam phonetics for brand names
            if any('\u0D00' <= c <= '\u0D7F' for c in text):
                text = re.sub(r"\bIVIA\b", "ഐവിയ", text, flags=re.IGNORECASE)
                text = re.sub(r"\bNextGenPro\b", "നെക്സ്റ്റ്ജെൻപ്രോ", text, flags=re.IGNORECASE)
                text = re.sub(r"\bEduPark\b", "എഡ്യൂപാർക്ക്", text, flags=re.IGNORECASE)
            else:
                text = re.sub(r"\bIVIA\b", IVIA_PHONETIC, text, flags=re.IGNORECASE)
                text = re.sub(r"\bEduPark\b", EDUPARK_PHONETIC, text, flags=re.IGNORECASE)
                text = re.sub(r"\bEdu\s*Park\b", EDUPARK_PHONETIC, text, flags=re.IGNORECASE)
                text = re.sub(r"\bNextGenPro\b", NEXTGENPRO_PHONETIC, text, flags=re.IGNORECASE)
        return text

    async def synthesize_to_pcm(self, text: str, target_lang: str = None) -> bytes:
        """
        Synthesizes text into 16kHz 16-bit Mono PCM bytes using Microsoft Edge TTS.
        Strictly enforces native Malayalam or English voice matching the target language.
        """
        if not text or not text.strip():
            return b""

        spoken_text = self._apply_phonetic_fixes(text.strip())
        
        # Enforce voice strictly: Malayalam (ml-IN-SobhanaNeural) or English (en-US-AriaNeural)
        if target_lang == "ml" or any('\u0D00' <= c <= '\u0D7F' for c in spoken_text):
            voice_to_use = TTS_VOICE_ML
        else:
            voice_to_use = self.default_voice

        cache_key = f"{voice_to_use}_{spoken_text}_{TTS_RATE}"
        if cache_key in self._cache:
            print(f"[TTS Cache HIT] Instant 0ms playback for: '{spoken_text[:40]}...'")
            return self._cache[cache_key]

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
            if pcm_bytes:
                self._cache[cache_key] = pcm_bytes
            print(f"[TTS] Synthesized {len(pcm_bytes)} PCM bytes ({len(pcm_bytes)/(SAMPLE_RATE*2):.1f}s audio)")
            return pcm_bytes

        except Exception as e:
            print(f"[TTS] Synthesis failed: {e}")
            return b""
