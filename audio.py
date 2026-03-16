# audio.py - I2S Audio: Microphone Recording + Speaker Playback
# ==============================================================
# INMP441 (I2S microphone) for recording
# MAX98357A (I2S DAC/amp) for playback
#
# IMPORTANT: Both mic and speaker share I2S bus 0 on ESP32-S3.
# Only one can be active at a time (time-multiplexed).
# This matches the working test scripts (micCheckWithSpectrum.py
# and speakerCheck.py) which both use I2S(0, ...).

from machine import I2S, Pin
import time
import struct

from config import (
    MIC_SCK_PIN, MIC_WS_PIN, MIC_SD_PIN,
    MIC_SAMPLE_RATE, MIC_BITS, MIC_BUFFER_SIZE,
    SPK_BCLK_PIN, SPK_LRC_PIN, SPK_DIN_PIN,
    SPK_SAMPLE_RATE, SPK_BITS,
    AUDIO_CHUNK_SIZE
)

# Shared I2S bus ID - both mic and speaker use bus 0
I2S_ID = 0


class Microphone:
    """I2S microphone (INMP441) reader."""

    def __init__(self):
        self.i2s = None
        self.running = False
        self.buffer = bytearray(AUDIO_CHUNK_SIZE)

    def init(self):
        """Initialize I2S for microphone input on bus 0."""
        if self.running:
            return True
        try:
            self.i2s = I2S(
                I2S_ID,
                sck=Pin(MIC_SCK_PIN),
                ws=Pin(MIC_WS_PIN),
                sd=Pin(MIC_SD_PIN),
                mode=I2S.RX,
                bits=MIC_BITS,
                format=I2S.MONO,
                rate=MIC_SAMPLE_RATE,
                ibuf=MIC_BUFFER_SIZE
            )
            self.running = True
            print(f"Microphone initialized: {MIC_SAMPLE_RATE}Hz, {MIC_BITS}-bit (I2S {I2S_ID})")
            return True
        except Exception as e:
            print(f"Mic init failed: {e}")
            self.running = False
            return False

    def read_chunk(self):
        """
        Read a chunk of audio data from the microphone.
        Returns bytes of raw PCM data, or None if not available.
        """
        if not self.running or not self.i2s:
            return None
        try:
            num_read = self.i2s.readinto(self.buffer)
            if num_read > 0:
                return bytes(self.buffer[:num_read])
        except Exception as e:
            print(f"Mic read error: {e}")
        return None

    def get_audio_level(self, data):
        """
        Calculate approximate audio level (0-100) from raw PCM data.
        Used for display visualization.
        """
        if not data or len(data) < 4:
            return 0
        total = 0
        samples = 0
        for i in range(0, min(len(data), 512), 2):
            if i + 1 < len(data):
                val = struct.unpack_from('<h', data, i)[0]
                total += abs(val)
                samples += 1

        if samples == 0:
            return 0

        avg = total / samples
        level = min(100, int(avg / 200))
        return level

    def deinit(self):
        """Release I2S resources so speaker can use bus 0."""
        if self.i2s:
            try:
                self.i2s.deinit()
            except Exception:
                pass
            self.i2s = None
        self.running = False
        print("Microphone deinitialized (I2S bus freed)")


class Speaker:
    """I2S speaker (MAX98357A) player."""

    def __init__(self):
        self.i2s = None
        self.running = False
        self.playing = False

    def init(self):
        """Initialize I2S for speaker output on bus 0."""
        if self.running:
            return True
        try:
            self.i2s = I2S(
                I2S_ID,
                sck=Pin(SPK_BCLK_PIN),
                ws=Pin(SPK_LRC_PIN),
                sd=Pin(SPK_DIN_PIN),
                mode=I2S.TX,
                bits=SPK_BITS,
                format=I2S.MONO,
                rate=SPK_SAMPLE_RATE,
                ibuf=4096
            )
            self.running = True
            print(f"Speaker initialized: {SPK_SAMPLE_RATE}Hz, {SPK_BITS}-bit (I2S {I2S_ID})")
            return True
        except Exception as e:
            print(f"Speaker init failed: {e}")
            self.running = False
            return False

    def play_raw(self, pcm_data):
        """
        Play raw PCM audio data (16-bit signed, mono).
        Blocking call - plays entire buffer.
        """
        if not self.running or not self.i2s:
            return
        try:
            self.playing = True
            self.i2s.write(pcm_data)
            self.playing = False
        except Exception as e:
            print(f"Playback error: {e}")
            self.playing = False

    def play_wav(self, wav_data):
        """
        Parse WAV header and play the PCM payload.
        Supports standard 16-bit PCM WAV files.
        """
        if not self.running or not self.i2s:
            return

        if len(wav_data) < 44:
            print("WAV data too short")
            return

        try:
            riff = wav_data[0:4]
            if riff != b'RIFF':
                print("Not a valid WAV file")
                return

            # Find 'data' chunk
            pos = 12
            data_start = None
            data_size = 0

            while pos < len(wav_data) - 8:
                chunk_id = wav_data[pos:pos + 4]
                chunk_size = struct.unpack_from('<I', wav_data, pos + 4)[0]

                if chunk_id == b'data':
                    data_start = pos + 8
                    data_size = chunk_size
                    break

                pos += 8 + chunk_size
                if chunk_size % 2 == 1:
                    pos += 1

            if data_start is None:
                print("No data chunk found in WAV")
                return

            pcm_data = wav_data[data_start:data_start + data_size]
            print(f"Playing WAV: {data_size} bytes of PCM data")
            self.play_raw(pcm_data)

        except Exception as e:
            print(f"WAV parse error: {e}")

    def play_wav_chunked(self, wav_data, chunk_size=1024):
        """
        Play WAV data in chunks (non-blocking friendly).
        Returns a generator that yields after each chunk.
        """
        if not self.running or not self.i2s or len(wav_data) < 44:
            return

        # Skip to data
        pos = 12
        while pos < len(wav_data) - 8:
            chunk_id = wav_data[pos:pos + 4]
            c_size = struct.unpack_from('<I', wav_data, pos + 4)[0]
            if chunk_id == b'data':
                data_start = pos + 8
                data_end = data_start + c_size
                break
            pos += 8 + c_size
            if c_size % 2 == 1:
                pos += 1
        else:
            return

        self.playing = True
        offset = data_start
        while offset < data_end and offset < len(wav_data):
            end = min(offset + chunk_size, data_end, len(wav_data))
            self.i2s.write(wav_data[offset:end])
            offset = end
            yield  # Let main loop breathe

        self.playing = False

    def stop(self):
        """Stop current playback."""
        self.playing = False

    def deinit(self):
        """Release I2S resources so mic can use bus 0."""
        if self.i2s:
            try:
                self.i2s.deinit()
            except Exception:
                pass
            self.i2s = None
        self.running = False
        self.playing = False
        print("Speaker deinitialized (I2S bus freed)")


# Test
if __name__ == "__main__":
    print("=== Audio Self-Test ===")
    print("Both mic and speaker share I2S bus 0")
    print()

    print("1. Testing Microphone...")
    mic = Microphone()
    mic.init()
    if mic.running:
        for i in range(10):
            data = mic.read_chunk()
            if data:
                level = mic.get_audio_level(data)
                bar = "#" * (level // 5)
                print(f"  Chunk {i}: {len(data)} bytes, level={level} {bar}")
            time.sleep_ms(100)
        mic.deinit()
        print("  Mic OK!")
    else:
        print("  Mic FAILED to init!")

    time.sleep_ms(100)  # Brief pause between bus switches

    print("\n2. Testing Speaker...")
    spk = Speaker()
    spk.init()
    if spk.running:
        import math
        import array
        # Generate tone matching the working test script
        SAMPLE_SIZE = 2000
        samples = array.array('h', [0] * SAMPLE_SIZE)
        for i in range(SAMPLE_SIZE):
            samples[i] = int(2000 * math.sin(2 * math.pi * 440 * i / SPK_SAMPLE_RATE))
        print("  Playing 440Hz test tone...")
        spk.i2s.write(samples)
        time.sleep_ms(500)
        spk.deinit()
        print("  Speaker OK!")
    else:
        print("  Speaker FAILED to init!")

    print("\nAudio test complete!")
