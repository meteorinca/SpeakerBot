from machine import I2S, Pin
import array
import time

# --- Configuration ---
MIC_SCK_PIN = 5      
MIC_WS_PIN  = 6      
MIC_SD_PIN  = 7      
SAMPLE_RATE = 16000  
READ_SIZE   = 512    # Increased for a better "window" of sound

# Setup I2S
audio_in = I2S(
    0,
    sck=Pin(MIC_SCK_PIN),
    ws=Pin(MIC_WS_PIN),
    sd=Pin(MIC_SD_PIN),
    mode=I2S.RX,
    bits=16,
    format=I2S.MONO,
    rate=SAMPLE_RATE,
    ibuf=2048
)

# Buffer for 16-bit signed integers ('h')
samples = array.array('h', [0] * READ_SIZE)

print("--- Starting Mic Visualizer ---")
print("Format: [Waveform Visualization] | Magnitude")
time.sleep(1)

try:
    while True:
        # Read a chunk of audio
        num_read = audio_in.readinto(samples)
        
        if num_read > 0:
            # 1. Calculate Peak-to-Peak (difference between loudest and quietest)
            # This is often more reactive for visualizations than a simple average.
            mx = max(samples)
            mn = min(samples)
            magnitude = mx - mn
            
            # 2. Create a simple text-based "Waveform"
            # We scale the magnitude to fit a 50-character wide bar
            # Adjust the '5000' divisor if your mic is very sensitive or very quiet
            bar_length = min(50, magnitude // 500) 
            waveform = "█" * bar_length
            
            # 3. Print the visualizer
            # The ':50' ensures the text doesn't jitter by keeping the width constant
            print(f"|{waveform:<50}| Mag: {magnitude}")
            
        else:
            print("No data received...")
            
        # Small delay to keep the serial console readable
        time.sleep(0.05)

except KeyboardInterrupt:
    print("\nStopping...")
finally:
    audio_in.deinit()
    print("I2S Deinitialized.")