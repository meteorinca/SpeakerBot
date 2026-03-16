# display.py - OLED Display for SpeakerBot (0.91" 128x32 SSD1306)
# =================================================================
# Shows status text, expressions, and audio visualizations.

from machine import Pin, I2C
import time

from config import OLED_SCL_PIN, OLED_SDA_PIN, OLED_WIDTH, OLED_HEIGHT, OLED_I2C_ID

# Try to import SSD1306 driver
try:
    import ssd1306
    SSD1306_AVAILABLE = True
except ImportError:
    SSD1306_AVAILABLE = False
    print("Warning: ssd1306 module not found. Display disabled.")


class Display:
    """
    OLED display manager for the SpeakerBot.
    
    0.91" 128x32 display - smaller than the Quadruped's 128x64,
    so we use text and simple icons instead of detailed eye animations.
    """

    # Face expressions (simple text-art for 128x32)
    FACE_IDLE = "^_^"
    FACE_HAPPY = "^v^"
    FACE_SAD = "T_T"
    FACE_ANGRY = ">_<"
    FACE_SURPRISED = "O_O"
    FACE_SLEEP = "-_-"
    FACE_LISTENING = "o_o"
    FACE_SPEAKING = "0_0"
    FACE_THINKING = "._."

    def __init__(self):
        self.display = None
        self.enabled = False
        self.current_face = self.FACE_IDLE
        self.idle_text = "Ready"
        self.status_line = self.idle_text
        self.show_audio_bar = False
        self.audio_level = 0
        self._last_draw = 0
        self._draw_interval = 100  # ms between redraws

        if SSD1306_AVAILABLE:
            try:
                i2c = I2C(OLED_I2C_ID, scl=Pin(OLED_SCL_PIN), sda=Pin(OLED_SDA_PIN),
                          freq=400000)
                self.display = ssd1306.SSD1306_I2C(OLED_WIDTH, OLED_HEIGHT, i2c)
                self.enabled = True
                print("OLED display initialized (128x32)")
            except Exception as e:
                print(f"Display init failed: {e}")

        if self.enabled:
            self.draw_boot_screen()

    def draw_boot_screen(self):
        """Show boot splash."""
        if not self.enabled:
            return
        self.display.fill(0)
        self.display.text("SpeakerBot", 24, 4, 1)
        self.display.text("v1.0", 48, 16, 1)
        self.display.show()

    def set_face(self, expression):
        """Set the face expression string."""
        self.current_face = expression

    def set_status(self, text):
        """Set the bottom status line."""
        self.status_line = text[:16]  # Max 16 chars at 8px font

    def set_audio_level(self, level):
        """Set audio level for visualization bar (0-100)."""
        self.audio_level = max(0, min(100, level))
        self.show_audio_bar = True

    def draw(self):
        """Main draw routine - shows face + status + optional audio bar."""
        if not self.enabled:
            return

        now = time.ticks_ms()
        if time.ticks_diff(now, self._last_draw) < self._draw_interval:
            return
        self._last_draw = now

        self.display.fill(0)

        # Row 1: Face expression (centered, large-ish)
        face_x = (OLED_WIDTH - len(self.current_face) * 8) // 2
        self.display.text(self.current_face, face_x, 2, 1)

        # Row 2: Status text or audio bar
        if self.show_audio_bar:
            # Draw audio level bar
            bar_width = int(self.audio_level * (OLED_WIDTH - 4) / 100)
            self.display.rect(1, 16, OLED_WIDTH - 2, 6, 1)
            if bar_width > 0:
                self.display.fill_rect(2, 17, bar_width, 4, 1)
            # Status below bar
            self.display.text(self.status_line, 0, 24, 1)
        else:
            # Just status text centered
            status_x = (OLED_WIDTH - len(self.status_line) * 8) // 2
            self.display.text(self.status_line, max(0, status_x), 20, 1)

        self.display.show()

    def show_ip(self, ip):
        """Show IP address on screen."""
        self.idle_text = ip if ip else "No WiFi"
        self.set_face("^_^")
        self.set_status(self.idle_text)
        self.draw()

    def show_listening(self):
        """Show listening state."""
        self.set_face(self.FACE_LISTENING)
        self.set_status("Listening...")
        self.show_audio_bar = True

    def show_speaking(self):
        """Show speaking/playback state."""
        self.set_face(self.FACE_SPEAKING)
        self.set_status("Playing...")
        self.show_audio_bar = True

    def show_idle(self):
        """Show idle state."""
        self.set_face(self.FACE_IDLE)
        self.set_status(self.idle_text)
        self.show_audio_bar = False

    def show_thinking(self):
        """Show processing/thinking state."""
        self.set_face(self.FACE_THINKING)
        self.set_status("Thinking...")
        self.show_audio_bar = False

    def show_error(self, msg="Error"):
        """Show error state."""
        self.set_face(self.FACE_ANGRY)
        self.set_status(msg[:16])
        self.show_audio_bar = False

    def clear(self):
        """Clear the display."""
        if self.enabled and self.display:
            self.display.fill(0)
            self.display.show()

    def update(self):
        """Call in main loop to refresh display."""
        self.draw()


# Test
if __name__ == "__main__":
    disp = Display()
    if disp.enabled:
        time.sleep(2)

        faces = [
            (Display.FACE_IDLE, "Idle"),
            (Display.FACE_HAPPY, "Happy!"),
            (Display.FACE_SAD, "Sad..."),
            (Display.FACE_ANGRY, "Angry!"),
            (Display.FACE_LISTENING, "Listening"),
            (Display.FACE_SPEAKING, "Playing"),
            (Display.FACE_SLEEP, "Zzz..."),
        ]

        for face, status in faces:
            disp.set_face(face)
            disp.set_status(status)
            disp.draw()
            time.sleep(1.5)

        # Audio bar demo
        disp.show_listening()
        for level in range(0, 101, 5):
            disp.set_audio_level(level)
            disp.draw()
            time.sleep_ms(50)

        disp.show_idle()
        disp.draw()
        print("Display test complete!")
