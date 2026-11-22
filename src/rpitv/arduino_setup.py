import json
from pathlib import Path


SETUP_JSON_PATH = Path(__file__).parent / "setup.json"
ARDUINO_SKETCH_PATH = Path(__file__).parent / "arduino_pixel"


def generate_arduino_config():
    config = json.loads(SETUP_JSON_PATH.read_text())

    header = (
        "#pragma once\n"
        f"constexpr int NUM_LEDS = {int(config['NUM_LEDS'])};\n"
        f"constexpr unsigned long BAUD_RATE = {int(config['BAUD_RATE'])};\n"
    )
    (ARDUINO_SKETCH_PATH / "config.h").write_text(header)

def build_upload_arduino_sketch():
    import subprocess
    import sys

    generate_arduino_config()

    # Compile the Arduino sketch
    compile_command = [
        "/home/pi/local/bin/arduino-cli",
        "compile",
        "--fqbn",
        "arduino:avr:nano:cpu=atmega328old",
        str(ARDUINO_SKETCH_PATH),
    ]
    subprocess.run(compile_command, check=True)

    # Upload the compiled sketch to the Arduino
    upload_command = [
        "/home/pi/local/bin/arduino-cli",
        "upload",
        "-p",
        "/dev/ttyUSB0",  # Adjust this to your Arduino's port
        "--fqbn",
        "arduino:avr:nano:cpu=atmega328old",
        str(ARDUINO_SKETCH_PATH),
    ]
    subprocess.run(upload_command, check=True)


if __name__ == "__main__":
    generate_arduino_config()