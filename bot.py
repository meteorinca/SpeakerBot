# bot.py - High-Level SpeakerBot Orchestration
# ================================================
import time
from servo import HeadServo
from display import Display
from audio import Microphone, Speaker
import led


class SpeakerBot:
    """
    Main bot class that coordinates all subsystems:
    - Head servo (left/right rotation)
    - OLED display (status, expressions)
    - Microphone (INMP441)
    - Speaker (MAX98357A)
    """

    def __init__(self):
        print("Initializing SpeakerBot...")
        self.head = HeadServo()
        self.display = Display()
        self.mic = Microphone()
        self.speaker = Speaker()

        self.streaming = False           # Is mic streaming active?
        self.last_update = time.ticks_ms()
        self.running = False

        # Playback state
        self._playback_gen = None        # Generator for chunked playback
        self._wav_buffer = bytearray()   # Accumulates incoming WAV chunks
        self._receiving_wav = False

        print("SpeakerBot initialized!")

    def start(self):
        """Start the bot in idle state."""
        self.running = True
        self.head.center()
        self.display.show_idle()
        self.display.draw()
        led.status_idle()

    def stop(self):
        """Shut everything down cleanly."""
        self.running = False
        self.streaming = False
        self.head.detach()
        self.mic.deinit()
        self.speaker.deinit()
        self.display.set_face(Display.FACE_SLEEP)
        self.display.set_status("Goodbye!")
        self.display.draw()

    def update(self):
        """Main update loop - call frequently."""
        self.head.update()

        # If doing chunked playback, advance it
        if self._playback_gen:
            try:
                next(self._playback_gen)
            except StopIteration:
                self._playback_gen = None
                self.display.show_idle()
                led.status_idle()

        self.display.update()
        led.update()

    # ==========================
    # HEAD COMMANDS
    # ==========================
    def turn_left(self, amount=1.0):
        self.head.look_left(amount)
        self.display.set_face(Display.FACE_IDLE)

    def turn_right(self, amount=1.0):
        self.head.look_right(amount)
        self.display.set_face(Display.FACE_IDLE)

    def center_head(self):
        self.head.center()

    def nod(self):
        self.head.nod_yes()
        self.display.set_face(Display.FACE_HAPPY)
        self.display.set_status("Yes!")

    def shake(self):
        self.head.shake_no()
        self.display.set_face(Display.FACE_SAD)
        self.display.set_status("No!")

    def set_head_angle(self, angle):
        self.head.set_target(angle)

    # ==========================
    # EXPRESSION COMMANDS
    # ==========================
    def happy(self):
        self.display.set_face(Display.FACE_HAPPY)
        self.display.set_status("Happy!")

    def sad(self):
        self.display.set_face(Display.FACE_SAD)
        self.display.set_status("Sad...")

    def angry(self):
        self.display.set_face(Display.FACE_ANGRY)
        self.display.set_status("Grr!")

    def surprised(self):
        self.display.set_face(Display.FACE_SURPRISED)
        self.display.set_status("Wow!")

    def sleep_mode(self):
        self.display.set_face(Display.FACE_SLEEP)
        self.display.set_status("Zzz...")
        self.streaming = False

    def wake(self):
        self.display.set_face(Display.FACE_SURPRISED)
        self.display.set_status("I'm awake!")
        self.streaming = True

    def idle(self):
        self.display.show_idle()
        led.status_idle()

    # ==========================
    # AUDIO COMMANDS
    # ==========================
    def start_streaming(self):
        """Start sending mic audio over UDP."""
        self.streaming = True
        self.display.show_listening()
        led.status_listening()

    def stop_streaming(self):
        """Stop mic streaming."""
        self.streaming = False
        self.display.show_idle()
        led.status_idle()

    def read_mic_chunk(self):
        """Read a chunk of mic audio. Returns bytes or None."""
        if not self.streaming:
            return None
        data = self.mic.read_chunk()
        if data:
            level = self.mic.get_audio_level(data)
            self.display.set_audio_level(level)
        return data

    def play_audio(self, wav_data):
        """Play a WAV file (blocking)."""
        self.display.show_speaking()
        self.display.draw()
        led.status_speaking()
        self.speaker.play_wav(wav_data)
        self.display.show_idle()
        led.status_idle()

    def play_audio_chunked(self, wav_data):
        """Start non-blocking WAV playback."""
        self.display.show_speaking()
        led.status_speaking()
        self._playback_gen = self.speaker.play_wav_chunked(wav_data)

    def begin_wav_receive(self):
        """Start accumulating WAV data from network."""
        self._wav_buffer = bytearray()
        self._receiving_wav = True
        self.display.show_thinking()
        led.status_thinking()

    def append_wav_data(self, chunk):
        """Append a chunk of incoming WAV data."""
        if self._receiving_wav:
            self._wav_buffer.extend(chunk)

    def finish_wav_receive(self):
        """Finish receiving and start playback."""
        self._receiving_wav = False
        if self._wav_buffer:
            self.play_audio_chunked(bytes(self._wav_buffer))
            self._wav_buffer = bytearray()

    # ==========================
    # DIAGNOSTICS
    # ==========================
    def test_audio(self):
        """Run audio diagnostic tests. Shows results on OLED and returns dict."""
        results = {}

        # --- Test Microphone ---
        self.display.set_face(self.display.FACE_LISTENING)
        self.display.set_status("Testing Mic...")
        self.display.draw()
        time.sleep_ms(300)

        mic_result = self.mic.test()
        results['mic'] = mic_result
        print(f"MIC TEST: init={mic_result['init']} read={mic_result['read_ok']} "
              f"signal={mic_result['has_signal']} avg={mic_result['avg_level']} "
              f"max={mic_result['max_level']} err={mic_result['error']}")

        if mic_result['pass']:
            self.display.set_status(f"Mic OK lvl:{mic_result['avg_level']}")
            self.display.set_face(self.display.FACE_HAPPY)
        else:
            self.display.set_status(f"Mic FAIL")
            self.display.set_face(self.display.FACE_ANGRY)
        self.display.draw()
        time.sleep(1)

        # --- Test Speaker ---
        self.display.set_face(self.display.FACE_SPEAKING)
        self.display.set_status("Testing Spkr...")
        self.display.draw()
        time.sleep_ms(300)

        spk_result = self.speaker.test()
        results['spk'] = spk_result
        print(f"SPK TEST: init={spk_result['init']} play={spk_result['play_ok']} "
              f"err={spk_result['error']}")

        if spk_result['pass']:
            self.display.set_status("Spkr OK")
            self.display.set_face(self.display.FACE_HAPPY)
        else:
            self.display.set_status(f"Spkr FAIL")
            self.display.set_face(self.display.FACE_ANGRY)
        self.display.draw()
        time.sleep(1)

        # --- Summary ---
        all_pass = mic_result['pass'] and spk_result['pass']
        if all_pass:
            self.display.set_face(self.display.FACE_HAPPY)
            self.display.set_status("Audio ALL OK!")
        else:
            fails = []
            if not mic_result['pass']:
                fails.append("MIC")
            if not spk_result['pass']:
                fails.append("SPK")
            self.display.set_face(self.display.FACE_SAD)
            self.display.set_status(f"FAIL: {'+'.join(fails)}")
        self.display.draw()
        time.sleep(2)

        # Return to idle
        self.display.show_idle()
        self.display.draw()

        results['all_pass'] = all_pass
        return results

    # ==========================
    # STATUS
    # ==========================
    def get_status(self):
        """Return a status dict."""
        return {
            "head_angle": self.head.get_angle(),
            "streaming": self.streaming,
            "playing": self.speaker.playing,
            "mic_ok": self.mic.running,
            "spk_ok": self.speaker.running,
            "display_ok": self.display.enabled,
        }


# Test
if __name__ == "__main__":
    bot = SpeakerBot()
    bot.start()

    print("Testing head movements...")
    bot.turn_left(0.5)
    for _ in range(50):
        bot.update()
        time.sleep_ms(20)

    bot.nod()
    for _ in range(100):
        bot.update()
        time.sleep_ms(20)

    bot.shake()
    for _ in range(100):
        bot.update()
        time.sleep_ms(20)

    bot.center_head()
    for _ in range(50):
        bot.update()
        time.sleep_ms(20)

    print("Status:", bot.get_status())
    bot.stop()
    print("Bot test complete!")
