# bot.py - High-Level SpeakerBot Orchestration
# ================================================
# IMPORTANT: Mic and Speaker share I2S bus 0.
# Only one can be active at a time. This file manages
# the switching between mic mode and speaker mode.

import time
import gc
from servo import HeadServo
from display import Display
from audio import Microphone, Speaker
import led


class SpeakerBot:
    """
    Main bot class that coordinates all subsystems:
    - Head servo (left/right rotation)
    - OLED display (status, expressions)
    - Microphone (INMP441) - shares I2S bus 0
    - Speaker (MAX98357A) - shares I2S bus 0
    """

    # Audio modes (only one I2S device active at a time)
    MODE_IDLE = 0
    MODE_MIC = 1
    MODE_SPEAKER = 2

    def __init__(self):
        print("Initializing SpeakerBot...")
        self.head = HeadServo()
        self.display = Display()
        self.mic = Microphone()
        self.speaker = Speaker()

        self.streaming = False
        self.last_update = time.ticks_ms()
        self.running = False
        self._audio_mode = self.MODE_IDLE

        print("SpeakerBot initialized!")
        gc.collect()

    # ==========================
    # I2S BUS MANAGEMENT
    # ==========================
    def _switch_to_mic(self):
        """Ensure mic is active on I2S bus 0. Deinit speaker first if needed."""
        if self._audio_mode == self.MODE_MIC:
            return True
        if self._audio_mode == self.MODE_SPEAKER:
            self.speaker.deinit()
            time.sleep_ms(50)
        ok = self.mic.init()
        if ok:
            self._audio_mode = self.MODE_MIC
            print("I2S bus -> MIC mode")
        return ok

    def _switch_to_speaker(self):
        """Ensure speaker is active on I2S bus 0. Deinit mic first if needed."""
        if self._audio_mode == self.MODE_SPEAKER:
            return True
        if self._audio_mode == self.MODE_MIC:
            self.mic.deinit()
            time.sleep_ms(50)
        ok = self.speaker.init()
        if ok:
            self._audio_mode = self.MODE_SPEAKER
            print("I2S bus -> SPEAKER mode")
        return ok

    def _release_audio(self):
        """Release I2S bus entirely."""
        if self._audio_mode == self.MODE_MIC:
            self.mic.deinit()
        elif self._audio_mode == self.MODE_SPEAKER:
            self.speaker.deinit()
        self._audio_mode = self.MODE_IDLE

    # ==========================
    # LIFECYCLE
    # ==========================
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
        self._release_audio()
        self.display.set_face(Display.FACE_SLEEP)
        self.display.set_status("Goodbye!")
        self.display.draw()

    def update(self):
        """Main update loop - call frequently."""
        self.head.update()
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
        self._release_audio()

    def wake(self):
        self.display.set_face(Display.FACE_SURPRISED)
        self.display.set_status("I'm awake!")
        # Don't auto-start streaming on wake, let LISTEN command do it

    def idle(self):
        self.display.show_idle()
        led.status_idle()

    # ==========================
    # AUDIO COMMANDS
    # ==========================
    def start_streaming(self):
        """Start sending mic audio over UDP. Switches I2S to mic mode."""
        if self._switch_to_mic():
            self.streaming = True
            self.display.show_listening()
            led.status_listening()
        else:
            self.display.show_error("Mic init err")
            self.display.draw()

    def stop_streaming(self):
        """Stop mic streaming."""
        self.streaming = False
        self.display.show_idle()
        led.status_idle()
        # Don't release I2S yet - keep mic warm in case we resume

    def read_mic_chunk(self):
        """Read a chunk of mic audio. Returns bytes or None."""
        if not self.streaming:
            return None
        if self._audio_mode != self.MODE_MIC:
            return None
        data = self.mic.read_chunk()
        if data:
            level = self.mic.get_audio_level(data)
            self.display.set_audio_level(level)
        return data

    def play_audio(self, wav_data):
        """Play a WAV file (blocking). Switches I2S to speaker mode."""
        was_streaming = self.streaming

        self.display.show_speaking()
        self.display.draw()
        led.status_speaking()

        if self._switch_to_speaker():
            self.speaker.play_wav(wav_data)
        else:
            print("Speaker init failed!")

        if was_streaming:
            self._switch_to_mic()
            self.display.show_listening()
            led.status_listening()
        else:
            self.display.show_idle()
            led.status_idle()

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

        # Switch to mic mode
        self._switch_to_mic()
        mic_result = {
            'name': 'Microphone',
            'init': self.mic.running,
            'read_ok': False,
            'has_signal': False,
            'avg_level': 0,
            'max_level': 0,
            'chunks_read': 0,
            'error': None,
            'pass': False,
        }
        if self.mic.running:
            try:
                levels = []
                for _ in range(10):
                    data = self.mic.read_chunk()
                    if data and len(data) > 0:
                        mic_result['chunks_read'] += 1
                        level = self.mic.get_audio_level(data)
                        levels.append(level)
                    time.sleep_ms(50)
                mic_result['read_ok'] = mic_result['chunks_read'] > 0
                if levels:
                    mic_result['avg_level'] = int(sum(levels) / len(levels))
                    mic_result['max_level'] = max(levels)
                    mic_result['has_signal'] = mic_result['max_level'] > 0
                mic_result['pass'] = mic_result['read_ok']
            except Exception as e:
                mic_result['error'] = str(e)
        else:
            mic_result['error'] = 'I2S init failed'

        results['mic'] = mic_result
        print(f"MIC TEST: init={mic_result['init']} read={mic_result['read_ok']} "
              f"signal={mic_result['has_signal']} avg={mic_result['avg_level']} "
              f"max={mic_result['max_level']} err={mic_result['error']}")

        if mic_result['pass']:
            self.display.set_status(f"Mic OK lvl:{mic_result['avg_level']}")
            self.display.set_face(self.display.FACE_HAPPY)
        else:
            self.display.set_status("Mic FAIL")
            self.display.set_face(self.display.FACE_ANGRY)
        self.display.draw()
        time.sleep(1)

        # --- Test Speaker ---
        self.display.set_face(self.display.FACE_SPEAKING)
        self.display.set_status("Testing Spkr...")
        self.display.draw()
        time.sleep_ms(300)

        # Switch to speaker mode (releases mic)
        self._switch_to_speaker()
        spk_result = {
            'name': 'Speaker',
            'init': self.speaker.running,
            'play_ok': False,
            'tone_hz': 440,
            'error': None,
            'pass': False,
        }
        if self.speaker.running:
            try:
                import math
                import array
                # Generate tone matching the working speakerCheck.py
                TONE_SAMPLES = 2000
                samples = array.array('h', [0] * TONE_SAMPLES)
                from config import SPK_SAMPLE_RATE
                for i in range(TONE_SAMPLES):
                    samples[i] = int(2000 * math.sin(2 * math.pi * 440 * i / SPK_SAMPLE_RATE))
                written = self.speaker.i2s.write(samples)
                time.sleep_ms(300)
                spk_result['play_ok'] = written > 0
                spk_result['bytes_written'] = written
                spk_result['pass'] = spk_result['play_ok']
            except Exception as e:
                spk_result['error'] = str(e)
        else:
            spk_result['error'] = 'I2S init failed'

        results['spk'] = spk_result
        print(f"SPK TEST: init={spk_result['init']} play={spk_result['play_ok']} "
              f"err={spk_result['error']}")

        if spk_result['pass']:
            self.display.set_status("Spkr OK")
            self.display.set_face(self.display.FACE_HAPPY)
        else:
            self.display.set_status("Spkr FAIL")
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

        # Release I2S bus and return to idle
        self._release_audio()
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
            "audio_mode": self._audio_mode,
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
