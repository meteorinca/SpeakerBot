from machine import I2S, Pin
import array
import math
import time

# Pin assignments (adjust if needed)
SPK_BCLK_PIN = 15   # I2S Bit Clock
SPK_LRC_PIN  = 16   # I2S Left/Right Clock
SPK_DIN_PIN  = 17   # I2S Data In

# I2S configuration
SAMPLE_RATE = 8000   # 8 kHz (low quality, but fine for testing)
SAMPLE_SIZE = 2000   # number of samples to generate (will play for ~0.25 sec at 8 kHz)
AMPLITUDE   = 2000   # low amplitude (max 32767 for 16‑bit) – safe level
FREQUENCY   = 440    # 440 Hz (A4)

# Create I2S object in TX mode
audio_out = I2S(
    0,                         # I2S peripheral id (0 or 1, depends on board)
    sck=Pin(SPK_BCLK_PIN),     # serial clock
    ws=Pin(SPK_LRC_PIN),       # word select
    sd=Pin(SPK_DIN_PIN),       # serial data output
    mode=I2S.TX,               # transmit mode
    bits=16,                   # 16‑bit samples
    format=I2S.MONO,           # mono (data sent to both channels)
    rate=SAMPLE_RATE,
    ibuf=2048                  # internal buffer size
)

# Generate a sine wave (16‑bit signed integers)
samples = array.array('h', [0] * SAMPLE_SIZE)
for i in range(SAMPLE_SIZE):
    # sin(2π * f / fs * i)
    samples[i] = int(AMPLITUDE * math.sin(2 * math.pi * FREQUENCY * i / SAMPLE_RATE))

# Play the tone (non‑blocking, but we'll wait for it to finish)
num_written = audio_out.write(samples)
print(f"Written {num_written} samples")

# Wait until all samples have been transmitted (approximate)
# The I2S write is asynchronous; we can wait a little longer than the duration.
duration = SAMPLE_SIZE / SAMPLE_RATE  # in seconds
time.sleep(duration + 0.1)

# Clean up
audio_out.deinit()
print("Test tone finished")