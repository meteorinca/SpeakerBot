# wifi.py - WiFi Connection Manager
# ====================================
import network
import time
from config import WIFI_SSID, WIFI_PASS
import led


def connect_wifi(display=None):
    """Connect to WiFi network. Returns IP string or None."""
    wlan = network.WLAN(network.STA_IF)

    if display:
        display.set_status("WiFi Init...")
        display.set_face(display.FACE_THINKING)
        display.draw()

    # Reset first
    wlan.active(False)
    time.sleep(1)

    try:
        wlan.active(True)
        print("WiFi radio active")
        time.sleep(3)  # ESP32-S3 needs settle time
    except Exception:
        print("WiFi activation failed")
        if display:
            display.show_error("WiFi Init Fail")
            display.draw()
        return None

    if not wlan.active():
        print("WiFi not started!")
        if display:
            display.show_error("WiFi Not Start")
            display.draw()
        return None

    # Disable power management for reliability
    try:
        wlan.config(pm=wlan.PM_NONE)
    except Exception:
        pass

    if wlan.isconnected():
        ip = wlan.ifconfig()[0]
        print(f"Already connected: {ip}")
        led.status_connected()
        if display:
            display.show_ip(ip)
        return ip

    print(f"Connecting to {WIFI_SSID}...")
    led.status_connecting()
    if display:
        display.set_status("Connecting...")
        display.set_face(display.FACE_THINKING)
        display.draw()
    wlan.connect(WIFI_SSID, WIFI_PASS)

    timeout = 400
    while not wlan.isconnected() and timeout > 0:
        time.sleep_ms(50)
        led.update()
        if display:
            display.update()
        timeout -= 1
        if timeout % 10 == 0:
            print(".", end="")

    if wlan.isconnected():
        ip = wlan.ifconfig()[0]
        print(f"\nConnected! IP: {ip}")
        led.status_connected()
        if display:
            display.show_ip(ip)
        return ip
    else:
        print("\nWiFi connection failed!")
        led.status_error()
        if display:
            display.show_error("WiFi Failed")
            display.draw()
        return None
