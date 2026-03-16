# udp_proxy.py - PC-side HTTP-to-UDP Proxy + Audio Receiver
# ============================================================
# Run this on your PC to:
#  1. Bridge web_controller.html (HTTP) to ESP32 (UDP commands)
#  2. Receive raw PCM audio stream from ESP32 mic
#  3. Send WAV files back to ESP32 for playback
#
# Usage: python udp_proxy.py

from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
import socket
import json
import time
import threading
import struct
import os
import wave
import io

UDP_CMD_PORT = 5005
UDP_AUDIO_PORT = 5006
UDP_PLAYBACK_PORT = 5007
HTTP_PORT = 8080
TIMEOUT = 2.0

# Audio recording settings (must match ESP32 config)
SAMPLE_RATE = 16000
SAMPLE_WIDTH = 2  # 16-bit = 2 bytes
CHANNELS = 1

# Global state
connection_state = {
    'last_successful_ip': None,
    'is_connected': False,
    'latency_ms': None,
    'total_commands': 0,
    'failed_commands': 0,
}

# Audio state
audio_state = {
    'recording': False,
    'audio_buffer': bytearray(),
    'total_bytes_received': 0,
    'last_audio_time': None,
    'saved_files': [],
}


class AudioReceiver(threading.Thread):
    """Background thread that receives raw PCM audio from ESP32 via UDP."""

    def __init__(self):
        super().__init__(daemon=True)
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.bind(('0.0.0.0', UDP_AUDIO_PORT))
        self.sock.settimeout(1.0)
        self.running = True
        print(f"🎤 Audio receiver listening on port {UDP_AUDIO_PORT}")

    def run(self):
        while self.running:
            try:
                data, addr = self.sock.recvfrom(4096)
                if data:
                    audio_state['total_bytes_received'] += len(data)
                    audio_state['last_audio_time'] = time.time()

                    if audio_state['recording']:
                        audio_state['audio_buffer'].extend(data)

            except socket.timeout:
                pass
            except Exception as e:
                if self.running:
                    print(f"Audio recv error: {e}")

    def stop(self):
        self.running = False
        self.sock.close()


def save_audio_to_wav(pcm_data, filename=None):
    """Save raw PCM bytes to a WAV file."""
    if not filename:
        os.makedirs('recordings', exist_ok=True)
        timestamp = time.strftime('%Y%m%d_%H%M%S')
        filename = f'recordings/rec_{timestamp}.wav'

    with wave.open(filename, 'wb') as wf:
        wf.setnchannels(CHANNELS)
        wf.setsampwidth(SAMPLE_WIDTH)
        wf.setframerate(SAMPLE_RATE)
        wf.writeframes(pcm_data)

    duration = len(pcm_data) / (SAMPLE_RATE * SAMPLE_WIDTH * CHANNELS)
    print(f"💾 Saved: {filename} ({duration:.1f}s, {len(pcm_data)} bytes)")
    audio_state['saved_files'].append(filename)
    return filename


def send_wav_to_bot(robot_ip, wav_filepath):
    """Send a WAV file to the ESP32 for playback."""
    try:
        with open(wav_filepath, 'rb') as f:
            wav_data = f.read()

        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        target = (robot_ip, UDP_PLAYBACK_PORT)

        # Signal start
        sock.sendto(b'WAV_START', target)
        time.sleep(0.05)

        # Send in chunks
        chunk_size = 1024
        offset = 0
        while offset < len(wav_data):
            end = min(offset + chunk_size, len(wav_data))
            sock.sendto(wav_data[offset:end], target)
            offset = end
            time.sleep(0.005)  # Small delay to not overwhelm ESP32

        # Signal end
        time.sleep(0.05)
        sock.sendto(b'WAV_END', target)
        sock.close()

        duration = len(wav_data) / (SAMPLE_RATE * SAMPLE_WIDTH * CHANNELS)
        print(f"📤 Sent WAV to {robot_ip}: {wav_filepath} ({len(wav_data)} bytes)")
        return True

    except Exception as e:
        print(f"Send WAV error: {e}")
        return False


class ProxyHandler(BaseHTTPRequestHandler):
    """Handle HTTP requests from web controller."""

    def do_GET(self):
        parsed = urlparse(self.path)

        if parsed.path == '/send':
            # Forward command to ESP32 via UDP
            params = parse_qs(parsed.query)
            robot_ip = params.get('ip', [''])[0]
            cmd = params.get('cmd', [''])[0]

            if not robot_ip or not cmd:
                self.send_error(400, 'Missing ip or cmd')
                return

            connection_state['total_commands'] += 1
            start_time = time.time()
            response = self.send_udp(robot_ip, cmd)
            latency = int((time.time() - start_time) * 1000)

            success = 'TIMEOUT' not in response and 'ERROR' not in response
            if success:
                connection_state['is_connected'] = True
                connection_state['last_successful_ip'] = robot_ip
                connection_state['latency_ms'] = latency
            else:
                connection_state['failed_commands'] += 1
                connection_state['is_connected'] = False

            self.send_json({'response': response, 'latency_ms': latency, 'connected': success})

        elif parsed.path == '/record/start':
            # Start recording audio from ESP32 mic
            audio_state['recording'] = True
            audio_state['audio_buffer'] = bytearray()
            self.send_json({'status': 'recording', 'message': 'Recording started'})

        elif parsed.path == '/record/stop':
            # Stop recording and save to WAV
            audio_state['recording'] = False
            buf = bytes(audio_state['audio_buffer'])
            audio_state['audio_buffer'] = bytearray()

            if buf:
                filename = save_audio_to_wav(buf)
                duration = len(buf) / (SAMPLE_RATE * SAMPLE_WIDTH * CHANNELS)
                self.send_json({
                    'status': 'saved',
                    'filename': filename,
                    'duration_s': round(duration, 1),
                    'bytes': len(buf)
                })
            else:
                self.send_json({'status': 'empty', 'message': 'No audio data received'})

        elif parsed.path == '/playback':
            # Send a WAV file to the ESP32 for playback
            params = parse_qs(parsed.query)
            robot_ip = params.get('ip', [''])[0]
            filepath = params.get('file', [''])[0]

            if not robot_ip or not filepath:
                self.send_error(400, 'Missing ip or file parameter')
                return

            if not os.path.exists(filepath):
                self.send_json({'status': 'error', 'message': f'File not found: {filepath}'})
                return

            success = send_wav_to_bot(robot_ip, filepath)
            self.send_json({'status': 'sent' if success else 'error'})

        elif parsed.path == '/recordings':
            # List saved recordings
            recordings = []
            rec_dir = 'recordings'
            if os.path.exists(rec_dir):
                for f in sorted(os.listdir(rec_dir)):
                    if f.endswith('.wav'):
                        path = os.path.join(rec_dir, f)
                        size = os.path.getsize(path)
                        duration = size / (SAMPLE_RATE * SAMPLE_WIDTH * CHANNELS)
                        recordings.append({
                            'filename': f,
                            'path': path,
                            'size': size,
                            'duration_s': round(duration, 1)
                        })
            self.send_json({'recordings': recordings})

        elif parsed.path == '/audio/status':
            # Get audio streaming status
            self.send_json({
                'total_bytes_received': audio_state['total_bytes_received'],
                'recording': audio_state['recording'],
                'buffer_size': len(audio_state['audio_buffer']),
                'last_audio_time': audio_state['last_audio_time'],
                'saved_count': len(audio_state.get('saved_files', []))
            })

        elif parsed.path == '/status':
            self.send_json({
                'proxy_running': True,
                'connected': connection_state['is_connected'],
                'last_ip': connection_state['last_successful_ip'],
                'latency_ms': connection_state['latency_ms'],
                'total_commands': connection_state['total_commands'],
                'failed_commands': connection_state['failed_commands'],
                'audio_bytes': audio_state['total_bytes_received'],
                'recording': audio_state['recording'],
            })

        elif parsed.path == '/ping':
            params = parse_qs(parsed.query)
            robot_ip = params.get('ip', [''])[0]
            if not robot_ip:
                self.send_error(400, 'Missing ip')
                return
            start_time = time.time()
            response = self.send_udp(robot_ip, 'PING')
            latency = int((time.time() - start_time) * 1000)
            self.send_json({
                'reachable': 'OK' in response,
                'response': response,
                'latency_ms': latency
            })

        elif parsed.path == '/':
            self.serve_status_page()

        else:
            self.send_error(404)

    def do_POST(self):
        """Handle POST requests for file upload."""
        parsed = urlparse(self.path)

        if parsed.path == '/playback/upload':
            # Upload a WAV file and send to bot
            params = parse_qs(parsed.query)
            robot_ip = params.get('ip', [''])[0]

            content_length = int(self.headers.get('Content-Length', 0))
            if content_length == 0:
                self.send_json({'status': 'error', 'message': 'No data'})
                return

            body = self.rfile.read(content_length)

            # Save temporarily
            os.makedirs('recordings', exist_ok=True)
            tmp_file = f'recordings/playback_{int(time.time())}.wav'
            with open(tmp_file, 'wb') as f:
                f.write(body)

            if robot_ip:
                success = send_wav_to_bot(robot_ip, tmp_file)
                self.send_json({'status': 'sent' if success else 'error', 'file': tmp_file})
            else:
                self.send_json({'status': 'saved', 'file': tmp_file})

        else:
            self.send_error(404)

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', '*')
        self.end_headers()

    def send_json(self, data):
        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()
        self.wfile.write(json.dumps(data).encode())

    def send_udp(self, robot_ip, cmd):
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            sock.settimeout(TIMEOUT)
            sock.sendto(cmd.encode(), (robot_ip, UDP_CMD_PORT))
            data, _ = sock.recvfrom(256)
            sock.close()
            return data.decode()
        except socket.timeout:
            return "TIMEOUT"
        except Exception as e:
            return f"ERROR: {e}"

    def serve_status_page(self):
        self.send_response(200)
        self.send_header('Content-Type', 'text/html')
        self.end_headers()
        is_connected = connection_state['is_connected']
        html = f'''<!DOCTYPE html>
<html><head><title>SpeakerBot Proxy</title>
<style>
body {{ font-family: 'Segoe UI', system-ui, sans-serif; background: #1a1a2e; color: #fff; padding: 40px; }}
h1 {{ color: #00d4ff; }}
.status {{ padding: 20px; background: rgba(255,255,255,0.05); border-radius: 12px; margin: 20px 0;
           border-left: 4px solid {"#00e676" if is_connected else "#ff5252"}; }}
.stat {{ margin: 10px 0; }}
.label {{ color: rgba(255,255,255,0.6); }}
code {{ background: rgba(0,0,0,0.3); padding: 2px 8px; border-radius: 4px; }}
</style></head><body>
<h1>🔊 SpeakerBot Proxy Running</h1>
<div class="status">
  <div class="stat"><span class="label">Status:</span> {"Connected" if is_connected else "Disconnected"}</div>
  <div class="stat"><span class="label">Robot IP:</span> {connection_state["last_successful_ip"] or "None"}</div>
  <div class="stat"><span class="label">Latency:</span> {connection_state["latency_ms"] or "---"}ms</div>
  <div class="stat"><span class="label">Commands:</span> {connection_state["total_commands"]}</div>
  <div class="stat"><span class="label">Audio bytes:</span> {audio_state["total_bytes_received"]}</div>
  <div class="stat"><span class="label">Recording:</span> {"Yes" if audio_state["recording"] else "No"}</div>
</div>
<h2>API Endpoints</h2>
<ul>
  <li><code>/send?ip=IP&cmd=CMD</code> - Send command</li>
  <li><code>/ping?ip=IP</code> - Ping robot</li>
  <li><code>/record/start</code> - Start recording mic audio</li>
  <li><code>/record/stop</code> - Stop recording, save WAV</li>
  <li><code>/recordings</code> - List saved recordings</li>
  <li><code>/playback?ip=IP&file=PATH</code> - Send WAV to robot</li>
  <li><code>/audio/status</code> - Audio streaming stats</li>
  <li><code>/status</code> - Full proxy status (JSON)</li>
</ul>
<p style="color: rgba(255,255,255,0.4); margin-top: 40px;">
  Open <code>web_controller.html</code> in your browser to control the bot.
</p>
<script>setTimeout(() => location.reload(), 5000);</script>
</body></html>'''
        self.wfile.write(html.encode())

    def log_message(self, format, *args):
        timestamp = time.strftime('%H:%M:%S')
        path = args[0].split()[1] if args and len(args[0].split()) > 1 else ''
        status = args[1] if len(args) > 1 else ''
        if '/send' in path:
            print(f"[{timestamp}] 📤 {path} -> {status}")
        elif '/record' in path:
            print(f"[{timestamp}] 🎤 {path} -> {status}")
        elif '/playback' in path:
            print(f"[{timestamp}] 🔊 {path} -> {status}")
        elif '/status' in path or '/ping' in path:
            pass  # Quiet for status checks
        else:
            print(f"[{timestamp}] {args[0]}")


def main():
    print("=" * 55)
    print("  🔊 SPEAKERBOT UDP PROXY")
    print("=" * 55)
    print(f"\n📡 HTTP server: http://localhost:{HTTP_PORT}")
    print(f"📤 Command port: {UDP_CMD_PORT}")
    print(f"🎤 Audio receive port: {UDP_AUDIO_PORT}")
    print(f"🔊 Playback send port: {UDP_PLAYBACK_PORT}")
    print(f"\n📋 Endpoints:")
    print(f"   /send?ip=IP&cmd=CMD    - Forward command")
    print(f"   /record/start          - Begin recording")
    print(f"   /record/stop           - Stop & save WAV")
    print(f"   /recordings            - List saved files")
    print(f"   /playback?ip=IP&file=F - Send WAV to bot")
    print(f"\n🌐 Open web_controller.html in your browser")
    print("⌨️  Ctrl+C to stop\n")
    print("-" * 55)

    # Start audio receiver thread
    audio_receiver = AudioReceiver()
    audio_receiver.start()

    # Start HTTP server
    server = HTTPServer(('0.0.0.0', HTTP_PORT), ProxyHandler)

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n\n🛑 Shutting down...")
        print(f"   Commands: {connection_state['total_commands']}")
        print(f"   Audio received: {audio_state['total_bytes_received']} bytes")
        audio_receiver.stop()
        server.shutdown()


if __name__ == "__main__":
    main()
