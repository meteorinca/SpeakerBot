import machine
import neopixel
import time
from config import LED_PIN

try:
    np = neopixel.NeoPixel(machine.Pin(LED_PIN, machine.Pin.OUT), 1)
except Exception as e:
    print("Warning: Failed to initialize NeoPixel:", e)
    np = None

_mode = 'solid'
_color1 = (0, 0, 0)
_color2 = (0, 0, 0)
_speed = 500
_last_toggle = 0
_toggle_state = False

def update():
    """Call this frequently in the main loop for animations."""
    global _last_toggle, _toggle_state
    if not np or _mode == 'solid':
        return
        
    now = time.ticks_ms()
    if time.ticks_diff(now, _last_toggle) > _speed:
        _toggle_state = not _toggle_state
        _last_toggle = now
        
        c = _color1 if _toggle_state else _color2
        try:
            np[0] = c
            np.write()
        except Exception:
            pass

def _set(mode, c1, c2=(0,0,0), speed=500):
    global _mode, _color1, _color2, _speed, _toggle_state
    _mode = mode
    _color1 = c1
    _color2 = c2
    _speed = speed
    _toggle_state = True
    if np:
        try:
            np[0] = c1
            np.write()
        except Exception:
            pass

def turn_off():
    _set('solid', (0, 0, 0))

def status_connecting():
    """Fast blinking blue for connecting to WiFi."""
    _set('blink', (0, 0, 50), (0, 0, 0), 200)

def status_connected():
    """Solid dim green for connected successfully."""
    _set('solid', (0, 20, 0))

def status_error():
    """Fast blinking red for connection error."""
    _set('blink', (50, 0, 0), (0, 0, 0), 200)

def status_idle():
    """Slow blinking cyan for idle."""
    _set('blink', (0, 10, 10), (0, 2, 2), 1000)

def status_listening():
    """Solid Yellow for listening."""
    _set('solid', (30, 30, 0))

def status_speaking():
    """Blinking green/blue for speaking."""
    _set('blink', (0, 30, 10), (0, 10, 30), 100)

def status_thinking():
    """Alternating purple/pink for processing/thinking."""
    _set('blink', (20, 0, 20), (10, 0, 30), 100)
