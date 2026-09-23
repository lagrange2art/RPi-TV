import logging
logger = logging.getLogger(__name__)

NUM_LEDS = 219
SERIAL_BAUD_RATE = 1000000
SERIAL_PING = bytes((0x10, 0x03))
SERIAL_RESPONSE = bytes((0x11, ord("R"), ord("P"), ord("I"), ord("T"), ord("V"), 0x03))


class LedStrip:
    def __init__(
            self,
            testing=False,
            count=NUM_LEDS,
            brightness=1.0,
            hardware: str = "rpi",
        ):
        self.testing = testing

        if testing:
            self._strip = FakeLedStrip(count, brightness)
            return

        if hardware == "rpi":
            try:
                import board
                import neopixel
            except ImportError as error:
                raise RuntimeError(
                    "NeoPixel hardware dependencies are required to use the LED strip on Raspberry Pi"
                ) from error

            self._strip = neopixel.NeoPixel(
                board.D10,
                count,
                brightness=brightness,
                auto_write=False,
            )

        elif hardware == "arduino":
            self._strip = ArduinoLedStrip(count, brightness)
        
        else:
            raise ValueError(f"Unsupported hardware: {hardware}. Choose 'rpi' or 'arduino'.")

    @property
    def brightness(self):
        return self._strip.brightness

    @brightness.setter
    def brightness(self, value):
        if not 0 <= value <= 1:
            raise ValueError("brightness must be between 0 and 1")
        self._strip.brightness = value
    
    def fill(self, color):
        self._strip.fill(color)

    def show(self):
        self._strip.show()

    def __len__(self):
        return len(self._strip)

    def __getitem__(self, key):
        return self._strip[key]

    def __setitem__(self, key, value):
        self._strip[key] = value

    def close(self):
        self.fill((0, 0, 0))
        self.show()

        close = getattr(self._strip, "deinit", None)
        if close is not None:
            close()

class FakeLedStrip:
    def __init__(self, count=NUM_LEDS, brightness=1.0):
        """Create an in-memory LED strip with the given size and brightness."""
        self.count = count
        self.brightness = brightness
        self._pixels = [(0, 0, 0)] * count

    def __getitem__(self, key):
        """Return the color at an index or for a slice of the strip."""
        return self._pixels[key]

    def __setitem__(self, index, val):
        """Allows setting colors via pixel[index] = (R, G, B)"""
        if isinstance(index, slice):
            start, stop, step = index.indices(self.count)
            indices = list(range(start, stop, step))
            values = list(val) if hasattr(val, "__iter__") else None

            if (
                values is not None
                and len(values) == len(indices)
                and all(hasattr(value, "__iter__") for value in values)
            ):
                for pixel_index, value in zip(indices, values):
                    self._pixels[pixel_index] = value
            else:
                for pixel_index in indices:
                    self._pixels[pixel_index] = val
        else:
            if 0 <= index < self.count:
                self._pixels[index] = val
            else:
                raise IndexError("LED index out of range")

    def fill(self, color):
        """Set every pixel in the strip to the given color."""
        self._pixels[:] = [color] * self.count

    def show(self):
        """Keep the in-memory strip state without sending it to hardware."""
        pass

    def __len__(self):
        """Return the number of LEDs in the strip."""
        return self.count

class ArduinoLedStrip(FakeLedStrip):
    def __init__(
        self,
        count: int = NUM_LEDS,
        brightness=1.0,
        baudrate=SERIAL_BAUD_RATE,
        port=None,
    ):
        import time

        import serial

        super().__init__(count, brightness)
        
        self.serial = None
        for serial_port in self._get_serial_ports(port):
            try:
                logger.info(f"trying serial port {serial_port}")
                connection = serial.Serial(
                    port=serial_port,
                    baudrate=baudrate,
                    timeout=1,
                )
                time.sleep(2)  # Give Arduino time to reset upon connection
                connection.reset_input_buffer()
                # serial handshake to verify connection, write and read
                connection.write(SERIAL_PING)
                connection.flush()
                response = connection.read(len(SERIAL_RESPONSE))
                if response == SERIAL_RESPONSE:
                    self.serial = connection
                    break
                logger.warning(
                    "Serial port %s failed Arduino validation; received %s, expected %s",
                    serial_port,
                    response.hex(" ") or "no bytes",
                    SERIAL_RESPONSE.hex(" "),
                )
                connection.close()
            except serial.SerialException as error:
                logger.warning("Could not open serial port %s: %s", serial_port, error)

        if self.serial is None:
            raise RuntimeError(
                "No Arduino responded to the serial validation ping. "
                "Check the connection and baud rate."
            )
        assert self.serial is not None

        self.brightness = brightness

    @property
    def brightness(self):
        return self._brightness

    @brightness.setter
    def brightness(self, value):
        if not 0 <= value <= 1:
            raise ValueError("brightness must be between 0 and 1")

        self._brightness = value
        if hasattr(self, "serial"):
            assert self.serial is not None
            brightness_byte = round(value * 255)
            self.serial.write(bytearray((0x01, brightness_byte, 0x03)))
            self.serial.flush()

    def _get_serial_ports(
            self,
            requested_port=None,
            ports=None
        ): #-> list[ListPortInfo]:
        """Return USB serial candidates without relying on an OS-specific number."""
        from pathlib import Path
        import serial.tools.list_ports

        if requested_port:
            if not Path(requested_port).exists():
                raise RuntimeError(f"Configured serial port {requested_port} does not exist")
            return [requested_port]

        discovered_ports = list(
            serial.tools.list_ports.comports() if ports is None else ports
        )
        usb_ports = [
            port for port in discovered_ports
            if Path(port.device).name.startswith(("ttyUSB", "ttyACM", "cu.usb"))
        ]

        if not usb_ports:
            available = ", ".join(port.device for port in discovered_ports if port.device)
            err_msg = (
                f"No USB serial port was found: {available or 'none'}. "
                "Connect the Arduino or set RPITV_SERIAL_PORT to its device path."
            )
            logger.error(err_msg)
            raise RuntimeError(err_msg)
        return [port.device for port in usb_ports]

    def show(self):
        """Send one framed RGB packet containing every LED's color."""
        assert self.serial is not None
        payload = bytearray((0x02,))

        for red, green, blue in self._pixels:
            payload.extend((int(red), int(green), int(blue)))

        payload.append(0x03)
        self.serial.write(payload)
        self.serial.flush()

    def close(self):
        assert self.serial is not None
        self.fill((0, 0, 0))
        self.show()
        self.serial.close()


class ADC:
    def __init__(self, testing=False):
        self._adc = FakeADC() if testing else ADS7830()
        self._closed = False

    def analogRead(self, channel):
        return self._adc.analogRead(channel)


    def close(self):
        if not self._closed:
            self._adc.close()
            self._closed = True


class ADS7830:
    def __init__(self):
        try:
            import smbus
        except ImportError as error:
            raise RuntimeError(
                "smbus is required to use the ADC on Raspberry Pi"
            ) from error

        self.cmd = 0x84
        self.address = 0x4B
        self.bus = smbus.SMBus(1)

    def analogRead(self, channel):
        return self.bus.read_byte_data(
            self.address,
            self.cmd | (((channel << 2 | channel >> 1) & 0x07) << 4),
        )

    def close(self):
        self.bus.close()


class FakeADC:
    def analogRead(self, channel):
        return 127

    def close(self):
        pass
