# config.py - SpeakerBot Pin & Hardware Configuration
# =====================================================
# All pin assignments for ESP32-S3
# Edit this file ONLY to change hardware wiring!

# ==========================
# SERVO (Head Turn)
# ==========================
SERVO_PIN = 1              # GPIO1 - Head rotation servo (PWM)
SERVO_MIN_ANGLE = 0        # Minimum angle (full left)
SERVO_MAX_ANGLE = 180      # Maximum angle (full right)
SERVO_CENTER = 90          # Center/neutral position
SERVO_SPEED = 2.0          # Degrees per update step (smoothing)

# PWM servo tuning (SG90 / MG90S typical)
SERVO_FREQ = 50            # 50Hz for standard servos
SERVO_MIN_US = 500         # Pulse width at 0 degrees (microseconds)
SERVO_MAX_US = 2500        # Pulse width at 180 degrees (microseconds)

# ==========================
# I2S MICROPHONE (INMP441)
# ==========================
MIC_SCK_PIN = 5            # GPIO5  - I2S Clock (SCK / BCLK)
MIC_WS_PIN = 6             # GPIO6  - I2S Word Select (WS / LRCLK)
MIC_SD_PIN = 7             # GPIO7  - I2S Serial Data (SD / DOUT)

MIC_SAMPLE_RATE = 16000    # 16kHz - good balance of quality/bandwidth
MIC_BITS = 16              # 16-bit samples
MIC_BUFFER_MS = 100        # Buffer size in milliseconds
MIC_BUFFER_SIZE = 3200     # MIC_SAMPLE_RATE * 2 (bytes per sample) * MIC_BUFFER_MS / 1000

# ==========================
# I2S SPEAKER (MAX98357A)
# ==========================
SPK_BCLK_PIN = 15          # GPIO15 - I2S Bit Clock
SPK_LRC_PIN = 16           # GPIO16 - I2S Left/Right Clock
SPK_DIN_PIN = 17           # GPIO17 - I2S Data In

SPK_SAMPLE_RATE = 16000    # 16kHz to match mic format
SPK_BITS = 16              # 16-bit output

# ==========================
# OLED DISPLAY (0.91" 128x32 SSD1306 I2C)
# ==========================
OLED_SCL_PIN = 42           # GPIO42 - I2C Clock
OLED_SDA_PIN = 41           # GPIO41 - I2C Data
OLED_WIDTH = 128           # pixels
OLED_HEIGHT = 32           # 0.91" displays are 128x32
OLED_I2C_ID = 0            # I2C bus 0

# ==========================
# NETWORK
# ==========================
try:
    from secrets import WIFI_SSID, WIFI_PASS
except ImportError:
    WIFI_SSID = "PUTWIFINAME"
    WIFI_PASS = "PUTWIFIPASSWORD"

UDP_CMD_PORT = 5005        # Incoming command port
UDP_AUDIO_PORT = 5006      # Outgoing mic audio stream port
UDP_PLAYBACK_PORT = 5007   # Incoming audio playback port

PC_IP = "192.168.1.100"    # Your PC's IP for audio streaming (EDIT THIS!)

# ==========================
# AUDIO STREAMING
# ==========================
AUDIO_CHUNK_SIZE = 1024    # Bytes per UDP audio packet
STREAM_ENABLED = True      # Enable/disable mic streaming on boot

# ==========================
# LED INDICATOR (WS2812 NeoPixel)
# ==========================
LED_PIN = 48               # Built-in RGB LED pin (often 48 on ESP32-S3)

# ==========================
# GENERAL
# ==========================
MAIN_LOOP_MS = 10          # Main loop interval (milliseconds)
HEARTBEAT_TIMEOUT_MS = 5000  # Client timeout for safety
