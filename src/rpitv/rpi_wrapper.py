import numpy as np
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
            target_count = len(range(start, stop, step))
            values = list(val) if hasattr(val, "__iter__") else None

            if (
                values is not None
                and len(values) == target_count
                and all(map(lambda value: hasattr(value, "__iter__"), values))
            ):
                self._pixels[index] = values
            elif len(val) == 3:
                self._pixels[index] = [val] * target_count
            else:
                raise IndexError(f"Cannot set {len(val)} rgb values to strip of length {self.count}")
        else:
            if index < 0:
                self._pixels[index + self.count] = val

            elif 0 <= index < self.count:
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


class FakePiCamera:
    def __init__(self):

        self._rng = np.random.default_rng()
               
        self.exposure_speed = 0
        self.awb_gains = (1.0, 1.0)
        self.closed = False
        self.resolution = (1, 1)
        self.iso = 400
        self.exposure_speed = 1
        self.shutter_speed = self.exposure_speed
        self.exposure_mode = "off"
        self.awb_gains = None
        self.awb_mode = "off"
        self.vflip = True
        self._continuous_counter = 0

    
    def capture(self,
                output,
                format=None,
                use_video_port=False,
                **kwargs
        ):
        """Write a black frame to an array-like capture target."""
        import numpy as np
        from pathlib import Path
        if isinstance(output, np.ndarray):
            if not format:
                raise RuntimeError("Format must be specified when output has no filename")
            # output[...] = self._rng.integers(
            #     0, 256,
            #     size=output.shape,
            #     dtype=np.uint8,
            # )
            return 
        elif isinstance(output, str):
            Path(output).touch()
        else:
            raise ValueError(f"cannot interprete output type {type(output)}")

    def capture_continuous(self, output, format=None, use_video_port=False, resize=None, splitter_port=0, burst=False, bayer=False, **options):
        """
        A dummy implementation of capture_continuous.
        Matches the exact signature, behavior, and generator type of picamera.

        Move a white box around
        """
        import numpy as np
        from matplotlib.pyplot import get_cmap
        from matplotlib import cm
        from matplotlib.colors import Normalize
        from matplotlib.image import imsave
        from pathlib import Path
        import time
        logger.info("Stream fake video")
        if not isinstance(output, np.ndarray):
            raise ValueError("FakePiCamera.capture_continuous requires a NumPy array")
        if not output.shape == (self.resolution[1], self.resolution[0], 3):
            raise ValueError(f"Expected output shape of {(self.resolution[1], self.resolution[0], 3)} got {output.shape} instead")
        box_size = 10
        max_x = self.resolution[0] - box_size
        max_y = self.resolution[1] - box_size
        perimeter = 2*(max_x + max_y)

        while True:
                        
            distance_from_origin = (self._continuous_counter) % perimeter

            # adjust mean rgb in each iteration
            output[:] = [0,0,0]

            # animate box
            if distance_from_origin < max_x:
                x, y = distance_from_origin, 0
            elif distance_from_origin < max_x + max_y:
                x, y = max_x, distance_from_origin - max_x
            elif distance_from_origin < 2 * max_x + max_y:
                x, y = 2 * max_x + max_y - distance_from_origin, max_y
            else:
                x, y = 0, perimeter - distance_from_origin

            box_color = [self._continuous_counter % 255, 0, 255 - self._continuous_counter % 255]
            output[y:y + box_size, x:x + box_size] = box_color

            # if self._continuous_counter % 10 == 0 and self._continuous_counter < 200:
            #     frame_path = f"/Users/tobiasb/Documents/RaspberryPi/rpitv/src/rpitv/static/ambilight_capture{self._continuous_counter:03d}.png"
            #     imsave(frame_path, output)

            self._continuous_counter += 1
            yield output            
    
    def close(self):
        self.closed = True

 
def _configure_camera(
        camera,
        capture_width:int,
        capture_height:int,
        framerate:int=30,
        iso:int=400,
        check_resolution_mismatch:bool=True,    
    ):
    import time
    import numpy as np

    # if check_resolution_mismatch:
    #     if capture_width % 32 != 0:
    #         raise ValueError(f"capture_width {capture_width} not supported. Choose multiple of 32")
    #     if capture_height % 16 != 0:
    #         raise ValueError(f"capture_height {capture_height} not supported. Choose multiple of 16")


    try:
        camera.resolution = (capture_width, capture_height)
        camera.framerate = framerate
        if not isinstance(camera, FakePiCamera):
            time.sleep(2)
        camera.iso = iso
        camera.shutter_speed = camera.exposure_speed
        camera.exposure_mode = "off"
        gain_set = camera.awb_gains
        camera.awb_mode = "off"
        camera.awb_gains = gain_set
        camera.vflip = True
    except Exception:
        try:
            camera.close()
        except Exception:
            logger.exception("Failed to close camera after configuration error")
        raise
    
    return camera


def PiCamera(
        capture_width:int,
        capture_height:int,
    ):
    """Return a configured Raspberry Pi camera or an equivalent fallback."""
    try:
        from picamera import PiCamera as _PiCamera
        return _configure_camera(_PiCamera(), capture_width, capture_height)
    except (ImportError, OSError, RuntimeError):
        logger.warning("PiCamera hardware unavailable; using fake camera")
        return _configure_camera(FakePiCamera(), capture_width, capture_height, check_resolution_mismatch=False)
