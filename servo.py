# servo.py - Single Head Servo Controller
# =========================================
from machine import Pin, PWM
import time

from config import (
    SERVO_PIN, SERVO_MIN_ANGLE, SERVO_MAX_ANGLE, SERVO_CENTER,
    SERVO_SPEED, SERVO_FREQ, SERVO_MIN_US, SERVO_MAX_US
)


class HeadServo:
    """Controls a single servo for head rotation with smooth movement."""

    def __init__(self):
        self.pwm = PWM(Pin(SERVO_PIN), freq=SERVO_FREQ)
        self.current_angle = SERVO_CENTER
        self.target_angle = SERVO_CENTER
        self.speed = SERVO_SPEED  # degrees per update
        self._set_angle(SERVO_CENTER)
        print(f"Head servo initialized on GPIO{SERVO_PIN}")

    def _angle_to_duty(self, angle):
        """Convert angle (0-180) to PWM duty cycle (16-bit)."""
        # Map angle to pulse width in microseconds
        pulse_us = SERVO_MIN_US + (angle / 180.0) * (SERVO_MAX_US - SERVO_MIN_US)
        # Convert to 16-bit duty (0-65535) at SERVO_FREQ Hz
        period_us = 1_000_000 / SERVO_FREQ
        duty = int((pulse_us / period_us) * 65535)
        return duty

    def _set_angle(self, angle):
        """Immediately set servo to angle."""
        angle = max(SERVO_MIN_ANGLE, min(SERVO_MAX_ANGLE, angle))
        self.pwm.duty_u16(self._angle_to_duty(angle))
        self.current_angle = angle

    def set_target(self, angle):
        """Set target angle for smooth movement."""
        self.target_angle = max(SERVO_MIN_ANGLE, min(SERVO_MAX_ANGLE, angle))

    def center(self):
        """Move head to center position."""
        self.set_target(SERVO_CENTER)

    def look_left(self, amount=1.0):
        """Turn head left. amount: 0.0-1.0"""
        angle = SERVO_CENTER + int(amount * (SERVO_MAX_ANGLE - SERVO_CENTER))
        self.set_target(angle)

    def look_right(self, amount=1.0):
        """Turn head right. amount: 0.0-1.0"""
        angle = SERVO_CENTER - int(amount * (SERVO_CENTER - SERVO_MIN_ANGLE))
        self.set_target(angle)

    def nod_yes(self):
        """Quick nod animation (non-blocking start, call update() to animate)."""
        # We'll use a simple oscillation pattern
        self._nod_steps = [
            SERVO_CENTER - 15, SERVO_CENTER + 15,
            SERVO_CENTER - 10, SERVO_CENTER + 10,
            SERVO_CENTER
        ]
        self._nod_index = 0
        self._nod_active = True

    def shake_no(self):
        """Shake head side to side."""
        self._shake_steps = [
            SERVO_CENTER + 30, SERVO_CENTER - 30,
            SERVO_CENTER + 20, SERVO_CENTER - 20,
            SERVO_CENTER
        ]
        self._shake_index = 0
        self._shake_active = True

    def update(self):
        """Smooth movement update. Call in main loop."""
        # Handle nod animation
        if hasattr(self, '_nod_active') and self._nod_active:
            if abs(self.current_angle - self.target_angle) < 2:
                if self._nod_index < len(self._nod_steps):
                    self.target_angle = self._nod_steps[self._nod_index]
                    self._nod_index += 1
                else:
                    self._nod_active = False

        # Handle shake animation
        if hasattr(self, '_shake_active') and self._shake_active:
            if abs(self.current_angle - self.target_angle) < 2:
                if self._shake_index < len(self._shake_steps):
                    self.target_angle = self._shake_steps[self._shake_index]
                    self._shake_index += 1
                else:
                    self._shake_active = False

        # Smooth movement toward target
        if abs(self.current_angle - self.target_angle) > 0.5:
            if self.current_angle < self.target_angle:
                self.current_angle = min(self.current_angle + self.speed,
                                         self.target_angle)
            else:
                self.current_angle = max(self.current_angle - self.speed,
                                         self.target_angle)
            self._set_angle(self.current_angle)

    def detach(self):
        """Release the servo (stop PWM signal)."""
        self.pwm.duty_u16(0)

    def get_angle(self):
        """Return current angle."""
        return int(self.current_angle)


# Test
if __name__ == "__main__":
    head = HeadServo()
    print("Center -> Left -> Right -> Center")

    head.center()
    for _ in range(50):
        head.update()
        time.sleep_ms(20)

    head.look_left(0.8)
    for _ in range(80):
        head.update()
        time.sleep_ms(20)

    head.look_right(0.8)
    for _ in range(80):
        head.update()
        time.sleep_ms(20)

    head.center()
    for _ in range(50):
        head.update()
        time.sleep_ms(20)

    head.detach()
    print("Done!")
