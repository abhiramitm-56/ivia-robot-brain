import io
import wave
import numpy as np

try:
    import miniaudio
except ImportError:
    miniaudio = None

try:
    import soundfile as sf
except ImportError:
    sf = None

from server.config import SAMPLE_RATE, CHANNELS, BYTES_PER_SAMPLE

def calculate_rms(pcm_data: bytes) -> float:
    """
    Calculate the Root Mean Square (RMS) energy of 16-bit PCM audio samples.
    Used for Voice Activity Detection (VAD).
    """
    if len(pcm_data) < 2:
        return 0.0
    # Read as 16-bit signed integers
    samples = np.frombuffer(pcm_data, dtype=np.int16)
    if len(samples) == 0:
        return 0.0
    mean_square = np.mean(samples.astype(np.float64) ** 2)
    return float(np.sqrt(mean_square))

def pcm_to_wav_bytes(pcm_data: bytes, sample_rate: int = SAMPLE_RATE, channels: int = CHANNELS) -> bytes:
    """
    Convert raw 16-bit PCM byte buffer into standard WAV formatted bytes.
    Removes DC offset and applies gentle AGC to maximize Whisper recognition accuracy.
    """
    if len(pcm_data) >= 4:
        samples = np.frombuffer(pcm_data, dtype=np.int16).astype(np.float32)
        # Remove DC bias from MEMS microphone
        samples -= np.mean(samples)
        # Dynamic normalization based on 98th percentile to boost soft voice and ignore transient pops
        p98 = float(np.percentile(np.abs(samples), 98))
        if p98 > 40.0:
            target = 22000.0
            gain = min(8.0, target / p98)
            samples *= gain
        pcm_data = np.clip(samples, -32768, 32767).astype(np.int16).tobytes()

    wav_io = io.BytesIO()
    with wave.open(wav_io, "wb") as wav_file:
        wav_file.setnchannels(channels)
        wav_file.setsampwidth(BYTES_PER_SAMPLE)
        wav_file.setframerate(sample_rate)
        wav_file.writeframes(pcm_data)
    return wav_io.getvalue()

def decode_audio_to_pcm16(audio_bytes: bytes, target_sample_rate: int = SAMPLE_RATE) -> bytes:
    """
    Decode MP3/WAV audio bytes into raw 16-bit signed mono PCM at target sample rate.
    Uses soundfile or miniaudio with standard wave fallback.
    """
    if not audio_bytes:
        return b""

    # Try miniaudio first if installed
    if miniaudio is not None:
        try:
            decoded = miniaudio.decode(
                audio_bytes,
                nchannels=1,
                sample_rate=target_sample_rate,
                output_format=miniaudio.SampleFormat.SIGNED16
            )
            return decoded.samples.tobytes()
        except Exception:
            pass

    # Try soundfile
    if sf is not None:
        try:
            audio_io = io.BytesIO(audio_bytes)
            data, sr = sf.read(audio_io, dtype="int16")
            if len(data.shape) > 1:
                data = data.mean(axis=1).astype(np.int16)
            if sr != target_sample_rate:
                try:
                    import scipy.signal
                    num_samples = int(len(data) * target_sample_rate / sr)
                    data = scipy.signal.resample(data, num_samples).astype(np.int16)
                except Exception:
                    pass
            return data.tobytes()
        except Exception:
            pass

    # Fallback if standard WAV
    try:
        with wave.open(io.BytesIO(audio_bytes), "rb") as wf:
            return wf.readframes(wf.getnframes())
    except Exception:
        return b""
