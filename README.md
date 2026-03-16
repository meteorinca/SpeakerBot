# 🔊 SpeakerBot - ESP32-S3 Voice-Enabled Static Robot

A MicroPython-based static robot with a rotating head, microphone, speaker, and OLED display. Streams voice input to a PC for processing and plays back audio responses — perfect as a voice assistant, intercom, or AI conversational bot platform.

> Inspired by the [MojQuadraped](../README.md) quadruped robot — same web-controller + UDP architecture, simplified to a desk buddy.

---

## Features

- 🤖 **Head Servo** — Single servo rotates head left/right with smooth animation (nod, shake)
- 🎤 **Microphone (INMP441)** — I2S digital mic, streams raw PCM to PC via UDP
- 🔊 **Speaker (MAX98357A)** — I2S DAC/amp, plays WAV files received from PC
- 📺 **OLED Display (0.91" SSD1306)** — Shows expressions, status, and audio level bars
- 📡 **WiFi + UDP** — Three-port UDP system: commands, mic stream, audio playback
- 🌐 **Web Controller** — Beautiful dark-themed web interface for full control
- 💻 **PC Proxy** — Python HTTP↔UDP bridge with mic recording and WAV playback

---

## 📌 ESP32-S3 Pin Assignments

### Head Servo (SG90 / MG90S)
| Function | GPIO | Notes |
|----------|------|-------|
| PWM Signal | **GPIO 1** | 50Hz PWM, 500-2500μs pulse |

### I2S Microphone (INMP441)
| Function | GPIO | INMP441 Pin |
|----------|------|-------------|
| SCK (Bit Clock) | **GPIO 5** | SCK / BCLK |
| WS (Word Select) | **GPIO 6** | WS / LRCLK |
| SD (Serial Data) | **GPIO 7** | SD / DOUT |
| VDD | 3.3V | Power |
| GND | GND | Ground |
| L/R | GND | Mono (left channel) |

### I2S Speaker (MAX98357A)
| Function | GPIO | MAX98357 Pin |
|----------|------|--------------|
| BCLK (Bit Clock) | **GPIO 15** | BCLK |
| LRC (L/R Clock) | **GPIO 16** | LRC |
| DIN (Data In) | **GPIO 17** | DIN |
| VIN | 5V | Power (use USB 5V or regulator) |
| GND | GND | Ground |
| GAIN | — | Leave floating (9dB) or wire to GND (12dB) |
| SD (Shutdown) | — | Leave floating (enabled) or pull HIGH |

### OLED Display (0.91" 128×32, SSD1306 I2C)
| Function | GPIO | SSD1306 Pin |
|----------|------|-------------|
| SCL (Clock) | **GPIO 9** | SCL / SCK |
| SDA (Data) | **GPIO 8** | SDA |
| VCC | 3.3V | Power |
| GND | GND | Ground |

### Pin Summary Diagram
```
ESP32-S3 Pin Map for SpeakerBot
================================

GPIO 1  ──── Servo PWM (Head)
GPIO 5  ──── INMP441 SCK
GPIO 6  ──── INMP441 WS
GPIO 7  ──── INMP441 SD
GPIO 8  ──── OLED SDA (I2C)
GPIO 9  ──── OLED SCL (I2C)
GPIO 15 ──── MAX98357 BCLK
GPIO 16 ──── MAX98357 LRC
GPIO 17 ──── MAX98357 DIN

Power:
3.3V ──── INMP441 VDD, OLED VCC
5V   ──── MAX98357 VIN
GND  ──── All GND pins
```

---

## 📁 File Structure

```
SpeakerBot/
├── main.py           # Entry point (clean imports only)
├── config.py         # All pin assignments & constants
├── wifi.py           # WiFi connection logic
├── servo.py          # Head servo controller
├── display.py        # OLED display manager
├── audio.py          # I2S mic (INMP441) + speaker (MAX98357A)
├── bot.py            # High-level bot orchestration
├── udp_server.py     # ESP32 UDP server (commands + audio streaming)
├── udp_proxy.py      # PC-side HTTP↔UDP proxy (run on PC!)
├── web_controller.html # Web interface (open in browser)
└── README.md         # This file
```

---

## 🚀 Quick Start

### 1. Edit Configuration
Open `config.py` and set:
```python
WIFI_SSID = "YourWiFiName"
WIFI_PASS = "YourWiFiPassword"
PC_IP = "192.168.1.100"  # Your PC's local IP
```

### 2. Upload to ESP32-S3
Using `mpremote`:
```bash
# Upload all .py files
mpremote connect COM18 cp config.py :config.py
mpremote connect COM18 cp wifi.py :wifi.py
mpremote connect COM18 cp servo.py :servo.py
mpremote connect COM18 cp display.py :display.py
mpremote connect COM18 cp audio.py :audio.py
mpremote connect COM18 cp bot.py :bot.py
mpremote connect COM18 cp udp_server.py :udp_server.py
mpremote connect COM18 cp main.py :main.py
```

Or upload all at once:
```bash
mpremote connect COM18 cp config.py wifi.py servo.py display.py audio.py bot.py udp_server.py main.py :
```

> **Note:** You also need the `ssd1306` driver on the ESP32. Install with:
> ```bash
> mpremote connect COM18 mip install ssd1306
> ```

### 3. Run on ESP32
```bash
mpremote connect COM18 run main.py
# Or just reset the board (main.py auto-runs)
```

### 4. Start PC Proxy
```bash
cd SpeakerBot
python udp_proxy.py
```
This starts the HTTP proxy at `http://localhost:8080`

### 5. Open Web Controller
Open `web_controller.html` in any browser, enter the ESP32's IP, and connect!

---

## 📡 Network Architecture

```
┌─────────────────────────────────────────────────────┐
│ Browser (web_controller.html)                       │
│   HTTP requests to proxy                            │
└───────────────┬─────────────────────────────────────┘
                │ HTTP (port 8080)
┌───────────────▼─────────────────────────────────────┐
│ PC: udp_proxy.py                                    │
│   ├─ HTTP→UDP command forwarding                    │
│   ├─ Receives raw PCM mic stream (port 5006)        │
│   ├─ Saves recordings as .wav files                 │
│   └─ Sends WAV files to ESP32 (port 5007)           │
└──┬──────────────────┬──────────────────┬────────────┘
   │ UDP:5005 (cmds)  │ UDP:5006 (mic)   │ UDP:5007 (play)
┌──▼──────────────────▼──────────────────▼────────────┐
│ ESP32-S3: SpeakerBot                                │
│   ├─ udp_server.py (receives commands)              │
│   ├─ audio.py (streams mic → PC, plays WAV)         │
│   ├─ servo.py (head rotation)                       │
│   └─ display.py (OLED status)                       │
└─────────────────────────────────────────────────────┘
```

### UDP Ports
| Port | Direction | Format | Purpose |
|------|-----------|--------|---------|
| **5005** | PC → ESP32 | Text (UTF-8) | Commands (`HEAD LEFT`, `HAPPY`, etc.) |
| **5006** | ESP32 → PC | Raw PCM (16-bit, 16kHz, mono) | Mic audio stream |
| **5007** | PC → ESP32 | WAV chunks + control signals | Speaker playback |

---

## 🎤 Audio Format Details

### Microphone Stream (ESP32 → PC)
- **Format:** Raw PCM (no header)
- **Bit depth:** 16-bit signed, little-endian
- **Sample rate:** 16,000 Hz
- **Channels:** Mono
- **Chunk size:** 1024 bytes per UDP packet (~32ms of audio)
- **Why raw PCM?** Lowest latency, zero overhead, trivial to work with

### Speaker Playback (PC → ESP32)
- **Format:** WAV (standard RIFF/WAVE with PCM data)
- **Bit depth:** 16-bit
- **Sample rate:** 16,000 Hz (recommended, but the WAV header specifies this)
- **Channels:** Mono
- **Why WAV?** Self-describing header, trivially parseable on MicroPython, no codec needed. MP3 would require a software decoder that MicroPython can't easily handle.

### Playback Protocol
```
PC sends: b'WAV_START'          → ESP32 begins buffering
PC sends: [WAV data chunk 1]   → ESP32 appends to buffer
PC sends: [WAV data chunk 2]   → ...
PC sends: [WAV data chunk N]   → ...
PC sends: b'WAV_END'           → ESP32 starts playback
```

---

## 🎮 Commands Reference

Send these via UDP to port 5005, or type in the web terminal.

### Head
| Command | Description |
|---------|-------------|
| `HEAD LEFT` | Turn head fully left |
| `HEAD LEFT 0.5` | Turn head 50% left |
| `HEAD RIGHT` | Turn head fully right |
| `HEAD CENTER` | Center head |
| `HEAD NOD` | Nod yes animation |
| `HEAD SHAKE` | Shake no animation |
| `HEAD 45` | Set head to 45° |

### Expressions (OLED)
| Command | Face | Description |
|---------|------|-------------|
| `HAPPY` | `^v^` | Happy face |
| `SAD` | `T_T` | Sad face |
| `ANGRY` | `>_<` | Angry face |
| `SURPRISED` | `O_O` | Surprised |
| `SLEEP` | `-_-` | Sleep mode |
| `WAKE` | `O_O` | Wake up |
| `IDLE` | `^_^` | Default idle |

### Audio
| Command | Description |
|---------|-------------|
| `LISTEN` | Start streaming mic to PC |
| `MUTE` | Stop mic streaming |

### System
| Command | Description |
|---------|-------------|
| `STATUS` / `PING` | Get bot status |
| `STOP` | Stop everything, return to idle |
| `HELP` | List available commands |

---

## 🔧 Hardware Assembly Notes

### INMP441 Wiring
- The INMP441 is a **3.3V** device — do NOT connect to 5V
- Connect the **L/R** pin to **GND** for left channel (mono) output
- The SCK, WS, SD pins go directly to ESP32 GPIOs

### MAX98357A Wiring
- The MAX98357A needs **5V** power (VIN) — use USB 5V or a regulator
- Logic pins (BCLK, LRC, DIN) are 3.3V compatible
- Leave **GAIN** pin floating for 9dB gain, or:
  - Connect to GND → 12dB
  - Connect to VIN → 15dB
- Leave **SD** (shutdown) pin floating to keep it enabled

### OLED 0.91" Display
- Standard I2C SSD1306, address 0x3C (default)
- Runs at 3.3V
- Uses 128×32 resolution (smaller than the quadruped's 128×64)

### Servo (SG90 / MG90S)
- Orange wire → GPIO 1 (signal)
- Red wire → 5V (power)
- Brown wire → GND
- If using MG90S (metal gear), it draws more current — consider a separate 5V supply

---

## 🧠 Processing Pipeline (Future)

The mic audio arrives on your PC as raw PCM saved to WAV files. Here's how to integrate processing:

```
1. ESP32 records mic → streams raw PCM over UDP (port 5006)
2. PC proxy receives and saves to recordings/rec_TIMESTAMP.wav
3. YOUR PROCESSING:
   - Speech-to-text (Whisper, Google STT, etc.)
   - AI response (GPT, local LLM, etc.)
   - Text-to-speech (generate response WAV)
4. Send response WAV back: /playback?ip=ESP32_IP&file=response.wav
5. ESP32 plays through MAX98357A speaker
```

### Example Python Processing Script (starter)
```python
import requests

PROXY = "http://localhost:8080"
BOT_IP = "192.168.1.42"

# Start mic streaming on bot
requests.get(f"{PROXY}/send?ip={BOT_IP}&cmd=LISTEN")

# Record 5 seconds
requests.get(f"{PROXY}/record/start")
import time; time.sleep(5)
result = requests.get(f"{PROXY}/record/stop").json()

print(f"Saved: {result['filename']}")

# TODO: Process with your STT/AI/TTS pipeline
# response_wav = your_ai_pipeline(result['filename'])

# Play response
# requests.get(f"{PROXY}/playback?ip={BOT_IP}&file={response_wav}")
```

---

## 📝 Troubleshooting

| Issue | Fix |
|-------|-----|
| OLED blank | Check I2C wiring, run `I2C(0, scl=Pin(9), sda=Pin(8)).scan()` |
| No mic audio | Check INMP441 L/R pin is connected to GND |
| Speaker silent | Check MAX98357 VIN is 5V, SD pin is floating/HIGH |
| WiFi fails | Increase settle time in `wifi.py`, check SSID/password |
| Servo jittering | Use separate 5V supply, add 100μF cap near servo |
| UDP packets lost | Reduce `AUDIO_CHUNK_SIZE` in config, check WiFi signal |

---

## 📦 Bill of Materials

| Component | Approx. Cost | Notes |
|-----------|-------------|-------|
| ESP32-S3 DevKit | $6-10 | Any S3 board with USB |
| INMP441 I2S Mic | $2-3 | Very common, 3.3V |
| MAX98357A I2S Amp | $2-4 | Includes DAC + 3W amp |
| Small Speaker (3W, 4Ω) | $1-2 | 28mm-40mm |
| SSD1306 OLED 0.91" | $2-3 | 128×32, I2C |
| SG90 Servo | $1-2 | Or MG90S for metal gears |
| Jumper Wires | $1 | |
| **Total** | **~$15-24** | |

---

## License

Same as parent project. Have fun building! 🤖🔊
