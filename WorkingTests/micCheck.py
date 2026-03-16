from machine import I2S, Pin
import array
import math

# Pin assignments (adjust if needed)
MIC_SCK_PIN = 5      # I2S Clock (BCLK)
MIC_WS_PIN  = 6      # I2S Word Select (LRCLK)
MIC_SD_PIN  = 7      # I2S Data (DIN)

# I2S configuration
SAMPLE_RATE = 16000  # 16 kHz
SAMPLE_SIZE = 256    # number of samples to read

# Create I2S object
audio_in = I2S(
    0,                        # I2S peripheral id (0 or 1, depends on board)
    sck=Pin(MIC_SCK_PIN),     # serial clock
    ws=Pin(MIC_WS_PIN),       # word select
    sd=Pin(MIC_SD_PIN),       # serial data (input)
    mode=I2S.RX,              # receive mode
    bits=16,                  # 16‑bit samples
    format=I2S.MONO,          # mono microphone
    rate=SAMPLE_RATE,
    ibuf=1024                 # internal buffer size
)

# Allocate sample buffer (16‑bit signed integers)
samples = array.array('h', [0] * SAMPLE_SIZE)

# Read one block of samples
num_read = audio_in.readinto(samples)

if num_read > 0:
    # Compute average absolute value (simple RMS)
    total = 0
    for s in samples:
        total += abs(s)
    avg = total / num_read
    print("Mic signal average:", avg)
    if avg < 10:
        print("Very low signal – check wiring or speak into the mic")
    else:
        print("Mic appears to be working")
else:
    print("No samples read – check connections")

# Clean up
audio_in.deinit()