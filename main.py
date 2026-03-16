# main.py - SpeakerBot Entry Point
# ===================================
# Clean entry point. All logic lives in imported modules.

import time
from wifi import connect_wifi
from config import UDP_CMD_PORT, MAIN_LOOP_MS


def main():
    """Main entry point for SpeakerBot."""
    print("=" * 40)
    print("  SPEAKERBOT v1.0")
    print("=" * 40)

    # Step 1: Connect to WiFi
    ip = connect_wifi()

    # Step 2: Initialize bot hardware
    from bot import SpeakerBot
    from udp_server import UDPServer

    bot = SpeakerBot()
    bot.start()

    if ip:
        # Show IP on display
        bot.display.show_ip(ip)
        time.sleep(2)

        # Step 3: Start UDP server
        server = UDPServer(bot)
        server.start()

        print(f"\nSpeakerBot ready at {ip}:{UDP_CMD_PORT}")
        print("Commands: HEAD LEFT/RIGHT/CENTER/NOD/SHAKE")
        print("          HAPPY, SAD, ANGRY, SLEEP, WAKE")
        print("          LISTEN, MUTE, STATUS")

        # Step 4: Main loop
        while True:
            try:
                server.update()
                bot.update()
                time.sleep_ms(MAIN_LOOP_MS)
            except KeyboardInterrupt:
                print("\nShutting down...")
                import led
                led.turn_off()
                bot.stop()
                server.stop()
                break
    else:
        # Offline mode
        print("\nOffline mode - no WiFi")
        bot.display.set_status("No WiFi")
        bot.display.set_face(">.< ")
        bot.display.draw()

        # Demo: nod and shake
        bot.nod()
        for _ in range(100):
            bot.update()
            time.sleep_ms(20)

        bot.shake()
        for _ in range(100):
            bot.update()
            time.sleep_ms(20)

        bot.center_head()

        # Keep running (update display)
        while True:
            try:
                bot.update()
                time.sleep_ms(MAIN_LOOP_MS)
            except KeyboardInterrupt:
                bot.stop()
                break


# Auto-run
if __name__ == "__main__":
    main()
