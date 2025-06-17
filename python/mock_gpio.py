# mock_gpio.py
# This is a mock version of the RPi.GPIO library for non-Raspberry Pi environments.
# It allows testing code that relies on GPIO without needing actual hardware.

class gpio:
    # Constants to simulate GPIO modes and states
    BCM = "BCM"          # Pin numbering scheme
    OUT = "OUT"          # Output mode
    HIGH = "HIGH"        # Pin state high
    LOW = "LOW"          # Pin state low

    # Dictionary to track the current state of each pin
    _pin_state = {}

    @staticmethod
    def setmode(mode):
        # Simulates setting the GPIO pin mode (e.g., BCM)
        print(f"[MOCK GPIO] Mode set to {mode}")

    @staticmethod
    def setwarnings(flag):
        # Simulates enabling or disabling GPIO warnings
        print(f"[MOCK GPIO] Warnings {'enabled' if flag else 'disabled'}")

    @staticmethod
    def setup(pin, mode):
        # Simulates setting up a pin as output
        print(f"[MOCK GPIO] Pin {pin} set as {mode}")
        gpio._pin_state[pin] = gpio.LOW

    @staticmethod
    def output(pin, state):
        # Simulates setting a pin to HIGH or LOW
        gpio._pin_state[pin] = state
        print(f"[MOCK GPIO] Pin {pin} set to {state}")

    @staticmethod
    def cleanup():
        # Simulates cleanup of GPIO settings
        print("[MOCK GPIO] Cleanup called")