# udp_server.py - UDP Network Server for SpeakerBot
# ====================================================
# Handles:
#  1. Command reception (port 5005) - text commands
#  2. Mic audio streaming to PC (port 5006) - raw PCM chunks
#  3. WAV audio reception from PC (port 5007) - STREAMING playback
#
# IMPORTANT: WAV playback is now streaming - chunks are played
# as they arrive, NOT buffered in RAM (ESP32 can't hold 500KB+).

import socket
import time
import gc

from config import (
    UDP_CMD_PORT, UDP_AUDIO_PORT, UDP_PLAYBACK_PORT,
    PC_IP, AUDIO_CHUNK_SIZE, HEARTBEAT_TIMEOUT_MS
)


class UDPServer:
    """Non-blocking UDP server that handles commands and audio streaming."""

    def __init__(self, bot, cmd_port=UDP_CMD_PORT):
        self.bot = bot
        self.cmd_port = cmd_port
        self.cmd_sock = None
        self.audio_sock = None       # For sending mic audio to PC
        self.playback_sock = None    # For receiving audio from PC
        self.running = False
        self.last_heartbeat = 0
        self.client_addr = None

        # Streaming playback state
        self._playing_stream = False
        self._wav_header_skipped = False
        self._stream_bytes = 0

    def start(self):
        """Start all UDP sockets."""
        self.cmd_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.cmd_sock.bind(('0.0.0.0', self.cmd_port))
        self.cmd_sock.setblocking(False)
        print(f"CMD server on port {self.cmd_port}")

        self.audio_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        print(f"Audio streaming target: {PC_IP}:{UDP_AUDIO_PORT}")

        self.playback_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.playback_sock.bind(('0.0.0.0', UDP_PLAYBACK_PORT))
        self.playback_sock.setblocking(False)
        print(f"Playback listener on port {UDP_PLAYBACK_PORT}")

        self.running = True

    def stop(self):
        """Stop all sockets."""
        self.running = False
        for sock in [self.cmd_sock, self.audio_sock, self.playback_sock]:
            if sock:
                try:
                    sock.close()
                except Exception:
                    pass

    def process_command(self, cmd):
        """Process a text command string."""
        parts = cmd.strip().upper().split()
        if not parts:
            return "ERR: Empty command"

        action = parts[0]
        args = parts[1:] if len(parts) > 1 else []

        # --- HEAD COMMANDS ---
        if action == "HEAD":
            if args:
                sub = args[0]
                if sub == "LEFT":
                    amount = float(args[1]) if len(args) > 1 else 1.0
                    self.bot.turn_left(amount)
                    return "OK: Head left"
                elif sub == "RIGHT":
                    amount = float(args[1]) if len(args) > 1 else 1.0
                    self.bot.turn_right(amount)
                    return "OK: Head right"
                elif sub == "CENTER":
                    self.bot.center_head()
                    return "OK: Head center"
                elif sub == "NOD":
                    self.bot.nod()
                    return "OK: Nodding"
                elif sub == "SHAKE":
                    self.bot.shake()
                    return "OK: Shaking"
                else:
                    try:
                        angle = int(sub)
                        self.bot.set_head_angle(angle)
                        return f"OK: Head={angle}"
                    except ValueError:
                        return f"ERR: Unknown HEAD sub-command '{sub}'"
            return "ERR: HEAD needs argument"

        # --- EXPRESSION COMMANDS ---
        elif action == "HAPPY":
            self.bot.happy()
            return "OK: Happy"
        elif action == "SAD":
            self.bot.sad()
            return "OK: Sad"
        elif action == "ANGRY":
            self.bot.angry()
            return "OK: Angry"
        elif action == "SURPRISED":
            self.bot.surprised()
            return "OK: Surprised"
        elif action == "SLEEP":
            self.bot.sleep_mode()
            return "OK: Sleeping"
        elif action == "WAKE":
            self.bot.wake()
            return "OK: Awake"
        elif action == "IDLE":
            self.bot.idle()
            return "OK: Idle"

        # --- AUDIO COMMANDS ---
        elif action == "LISTEN":
            self.bot.start_streaming()
            return "OK: Streaming mic"
        elif action == "MUTE":
            self.bot.stop_streaming()
            return "OK: Mic muted"

        # --- SYSTEM ---
        elif action == "STATUS" or action == "PING":
            status = self.bot.get_status()
            return f"OK: H={status['head_angle']} MIC={'ON' if status['streaming'] else 'OFF'}"
        elif action == "HELP":
            return "CMDS: HEAD(LEFT/RIGHT/CENTER/NOD/SHAKE/angle) HAPPY SAD ANGRY SLEEP WAKE LISTEN MUTE STATUS"
        elif action == "STOP":
            self._stop_playback_stream()
            self.bot.stop_streaming()
            self.bot.center_head()
            self.bot.idle()
            return "OK: Stopped"

        # --- DIAGNOSTICS ---
        elif action == "TEST":
            if args and args[0] == "AUDIO":
                results = self.bot.test_audio()
                m = results['mic']
                s = results['spk']
                return (f"OK: ALL={results['all_pass']} "
                        f"MIC(init={m['init']},read={m['read_ok']},signal={m['has_signal']},avg={m['avg_level']},max={m['max_level']},pass={m['pass']},err={m['error']}) "
                        f"SPK(init={s['init']},play={s['play_ok']},pass={s['pass']},err={s['error']})")
            else:
                return "ERR: TEST needs AUDIO"

        else:
            return f"ERR: Unknown '{action}'"

    # ==========================
    # STREAMING PLAYBACK
    # ==========================
    def _start_playback_stream(self):
        """Begin streaming playback - switch I2S to speaker mode."""
        # Stop mic if it's running
        if self.bot.streaming:
            self.bot.stop_streaming()

        # Switch to speaker
        if self.bot._switch_to_speaker():
            self._playing_stream = True
            self._wav_header_skipped = False
            self._stream_bytes = 0
            self.bot.display.show_speaking()
            self.bot.display.draw()
            gc.collect()
            print("Stream playback started")
        else:
            print("Failed to init speaker for stream!")

    def _stop_playback_stream(self):
        """End streaming playback."""
        if self._playing_stream:
            self._playing_stream = False
            self.bot.speaker.playing = False
            print(f"Stream playback done: {self._stream_bytes} bytes played")
            self.bot.display.show_idle()
            self.bot.display.draw()
            gc.collect()

    def _play_stream_chunk(self, data):
        """Play a chunk of audio data directly to speaker (no buffering)."""
        if not self._playing_stream or not self.bot.speaker.running:
            return

        pcm_data = data

        # First chunk: skip WAV header (44 bytes)
        if not self._wav_header_skipped:
            # Check if it starts with RIFF header
            if len(data) > 44 and data[:4] == b'RIFF':
                pcm_data = data[44:]
                self._wav_header_skipped = True
                print(f"  Skipped WAV header, playing {len(pcm_data)} bytes")
            else:
                # No header - play as raw PCM
                self._wav_header_skipped = True

        if len(pcm_data) > 0:
            try:
                self.bot.speaker.playing = True
                self.bot.speaker.i2s.write(pcm_data)
                self._stream_bytes += len(pcm_data)
            except Exception as e:
                print(f"Stream play error: {e}")

    # ==========================
    # MIC STREAMING
    # ==========================
    def stream_mic_audio(self):
        """Read mic data and send to PC via UDP."""
        if not self.bot.streaming or not self.audio_sock:
            return
        if self.bot._audio_mode != self.bot.MODE_MIC:
            return

        try:
            data = self.bot.read_mic_chunk()
            if data:
                self.audio_sock.sendto(data, (PC_IP, UDP_AUDIO_PORT))
        except Exception as e:
            print(f"Audio send error: {e}")

    # ==========================
    # PLAYBACK RECEIVE
    # ==========================
    def check_playback(self):
        """Check for incoming WAV audio data from PC. Plays as it streams."""
        if not self.playback_sock:
            return

        # Read multiple packets per update for smoother playback
        for _ in range(5):
            try:
                data, addr = self.playback_sock.recvfrom(2048)
                if not data:
                    return

                if data == b'WAV_START':
                    self._start_playback_stream()
                    print("Receiving WAV stream from PC...")
                elif data == b'WAV_END':
                    self._stop_playback_stream()
                    print("WAV stream complete")
                else:
                    # Play this chunk immediately - no buffering!
                    self._play_stream_chunk(data)

            except OSError:
                break  # No more data

    # ==========================
    # MAIN UPDATE
    # ==========================
    def update(self):
        """Main update - check commands, stream audio, check playback."""
        if not self.running:
            return

        # 1. Check for commands (always responsive)
        try:
            data, addr = self.cmd_sock.recvfrom(256)
            self.client_addr = addr
            self.last_heartbeat = time.ticks_ms()

            cmd = data.decode('utf-8')
            response = self.process_command(cmd)

            self.cmd_sock.sendto(response.encode('utf-8'), addr)
            print(f"[{addr[0]}] {cmd.strip()} -> {response}")

        except OSError:
            pass

        # 2. Stream mic audio (only if in mic mode)
        if not self._playing_stream:
            self.stream_mic_audio()

        # 3. Check for incoming playback audio
        self.check_playback()

        # 4. Safety timeout
        if self.client_addr and self.last_heartbeat:
            if time.ticks_diff(time.ticks_ms(), self.last_heartbeat) > HEARTBEAT_TIMEOUT_MS:
                self.last_heartbeat = 0


# Test
if __name__ == "__main__":
    from bot import SpeakerBot

    bot = SpeakerBot()
    bot.start()

    server = UDPServer(bot)
    server.start()

    print("UDP Server running. Send commands to port", UDP_CMD_PORT)
    while True:
        try:
            server.update()
            bot.update()
            time.sleep_ms(10)
        except KeyboardInterrupt:
            print("\nShutting down...")
            bot.stop()
            server.stop()
            break
