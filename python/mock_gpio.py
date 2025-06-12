# mock_gpio.py

class gpio:
    BCM = "BCM"
    OUT = "OUT"
    HIGH = "HIGH"
    LOW = "LOW"

    _pin_state = {}

    @staticmethod
    def setmode(mode):
        print(f"[MOCK GPIO] Mode set to {mode}")

    @staticmethod
    def setwarnings(flag):
        print(f"[MOCK GPIO] Warnings {'enabled' if flag else 'disabled'}")

    @staticmethod
    def setup(pin, mode):
        print(f"[MOCK GPIO] Pin {pin} set as {mode}")
        gpio._pin_state[pin] = gpio.LOW

    @staticmethod
    def output(pin, state):
        gpio._pin_state[pin] = state
        print(f"[MOCK GPIO] Pin {pin} set to {state}")

    @staticmethod
    def cleanup():
        print("[MOCK GPIO] Cleanup called")