# wifi.py - WiFi Connection Manager
# ====================================
import network
import time
from config import WIFI_SSID, WIFI_PASS
import led


def connect_wifi():
    """Connect to WiFi network. Returns IP string or None."""
    wlan = network.WLAN(network.STA_IF)

    # Reset first
    wlan.active(False)
    time.sleep(1)

    try:
        wlan.active(True)
        print("WiFi radio active")
        time.sleep(3)  # ESP32-S3 needs settle time
    except Exception:
        print("WiFi activation failed")
        return None

    if not wlan.active():
        print("WiFi not started!")
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
        return ip

    print(f"Connecting to {WIFI_SSID}...")
    led.status_connecting()
    wlan.connect(WIFI_SSID, WIFI_PASS)

    timeout = 400
    while not wlan.isconnected() and timeout > 0:
        time.sleep_ms(50)
        led.update()
        timeout -= 1
        if timeout % 10 == 0:
            print(".", end="")

    if wlan.isconnected():
        ip = wlan.ifconfig()[0]
        print(f"\nConnected! IP: {ip}")
        led.status_connected()
        return ip
    else:
        print("\nWiFi connection failed!")
        led.status_error()
        return None
