# audio.py - I2S Audio: Microphone Recording + Speaker Playback
# ==============================================================
# INMP441 (I2S microphone) for recording
# MAX98357A (I2S DAC/amp) for playback
#
# Audio format: Raw PCM 16-bit signed, 16kHz, mono
# WAV playback: Parses standard WAV header then plays PCM data

from machine import I2S, Pin
import time
import struct

from config import (
    MIC_SCK_PIN, MIC_WS_PIN, MIC_SD_PIN,
    MIC_SAMPLE_RATE, MIC_BITS, MIC_CHANNEL, MIC_BUFFER_SIZE,
    SPK_BCLK_PIN, SPK_LRC_PIN, SPK_DIN_PIN,
    SPK_SAMPLE_RATE, SPK_BITS, SPK_CHANNEL,
    AUDIO_CHUNK_SIZE
)


class Microphone:
    """I2S microphone (INMP441) reader."""

    def __init__(self):
        self.i2s = None
        self.running = False
        self.buffer = bytearray(AUDIO_CHUNK_SIZE)
        self._init_i2s()

    def _init_i2s(self):
        """Initialize I2S for microphone input."""
        try:
            self.i2s = I2S(
                MIC_CHANNEL,
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
            print(f"Microphone initialized: {MIC_SAMPLE_RATE}Hz, {MIC_BITS}-bit")
        except Exception as e:
            print(f"Mic init failed: {e}")
            self.running = False

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
        # Sample a few values to get RMS-ish level
        total = 0
        samples = 0
        for i in range(0, min(len(data), 512), 2):
            if i + 1 < len(data):
                # 16-bit signed little-endian
                val = struct.unpack_from('<h', data, i)[0]
                total += abs(val)
                samples += 1

        if samples == 0:
            return 0

        avg = total / samples
        # Scale to 0-100 (INMP441 output is typically in the thousands range)
        level = min(100, int(avg / 200))
        return level

    def test(self):
        """Run microphone diagnostic. Returns dict with results."""
        result = {
            'name': 'Microphone',
            'init': self.running,
            'read_ok': False,
            'has_signal': False,
            'avg_level': 0,
            'max_level': 0,
            'chunks_read': 0,
            'error': None,
            'pass': False,
        }
        if not self.running or not self.i2s:
            result['error'] = 'I2S init failed'
            return result

        try:
            levels = []
            for _ in range(10):
                data = self.read_chunk()
                if data and len(data) > 0:
                    result['chunks_read'] += 1
                    level = self.get_audio_level(data)
                    levels.append(level)
                time.sleep_ms(50)

            result['read_ok'] = result['chunks_read'] > 0
            if levels:
                result['avg_level'] = int(sum(levels) / len(levels))
                result['max_level'] = max(levels)
                # If we get any level > 0, there's signal (even noise)
                result['has_signal'] = result['max_level'] > 0

            result['pass'] = result['read_ok']
        except Exception as e:
            result['error'] = str(e)

        return result

    def deinit(self):
        """Release I2S resources."""
        if self.i2s:
            self.i2s.deinit()
            self.running = False
            print("Microphone deinitialized")


class Speaker:
    """I2S speaker (MAX98357A) player."""

    def __init__(self):
        self.i2s = None
        self.running = False
        self.playing = False
        self._init_i2s()

    def _init_i2s(self):
        """Initialize I2S for speaker output."""
        try:
            self.i2s = I2S(
                SPK_CHANNEL,
                sck=Pin(SPK_BCLK_PIN),
                ws=Pin(SPK_LRC_PIN),
                sd=Pin(SPK_DIN_PIN),
                mode=I2S.TX,
                bits=SPK_BITS,
                format=I2S.MONO,
                rate=SPK_SAMPLE_RATE,
                ibuf=8192  # Larger buffer for smooth playback
            )
            self.running = True
            print(f"Speaker initialized: {SPK_SAMPLE_RATE}Hz, {SPK_BITS}-bit")
        except Exception as e:
            print(f"Speaker init failed: {e}")
            self.running = False

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

        # Parse WAV header
        try:
            riff = wav_data[0:4]
            if riff != b'RIFF':
                print("Not a valid WAV file")
                return

            # Find 'data' chunk
            pos = 12  # Skip RIFF header
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
                # Align to even boundary
                if chunk_size % 2 == 1:
                    pos += 1

            if data_start is None:
                print("No data chunk found in WAV")
                return

            # Play the PCM data
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

    def test(self):
        """Run speaker diagnostic. Returns dict with results."""
        import math
        result = {
            'name': 'Speaker',
            'init': self.running,
            'play_ok': False,
            'tone_hz': 440,
            'duration_ms': 500,
            'error': None,
            'pass': False,
        }
        if not self.running or not self.i2s:
            result['error'] = 'I2S init failed'
            return result

        try:
            # Generate 440Hz tone for 0.5s
            num_samples = SPK_SAMPLE_RATE // 2  # 0.5 seconds
            buf = bytearray(num_samples * 2)  # 16-bit = 2 bytes per sample
            for i in range(num_samples):
                t = i / SPK_SAMPLE_RATE
                val = int(8000 * math.sin(2 * math.pi * 440 * t))
                struct.pack_into('<h', buf, i * 2, val)

            self.playing = True
            written = self.i2s.write(buf)
            self.playing = False

            result['play_ok'] = written > 0
            result['bytes_written'] = written
            result['pass'] = result['play_ok']
        except Exception as e:
            result['error'] = str(e)
            self.playing = False

        return result

    def deinit(self):
        """Release I2S resources."""
        if self.i2s:
            self.i2s.deinit()
            self.running = False
            print("Speaker deinitialized")


# Test
if __name__ == "__main__":
    print("Testing Microphone...")
    mic = Microphone()
    if mic.running:
        # Read a few chunks
        for i in range(10):
            data = mic.read_chunk()
            if data:
                level = mic.get_audio_level(data)
                bar = "#" * (level // 5)
                print(f"  Chunk {i}: {len(data)} bytes, level={level} {bar}")
            time.sleep_ms(100)
        mic.deinit()

    print("\nTesting Speaker...")
    spk = Speaker()
    if spk.running:
        # Generate a simple test tone (440Hz sine-ish)
        import math
        samples = bytearray(SPK_SAMPLE_RATE)  # 0.5 seconds
        for i in range(0, len(samples), 2):
            t = (i // 2) / SPK_SAMPLE_RATE
            val = int(8000 * math.sin(2 * math.pi * 440 * t))
            struct.pack_into('<h', samples, i, val)
        print("  Playing 440Hz test tone...")
        spk.play_raw(samples)
        spk.deinit()

    print("Audio test complete!")
