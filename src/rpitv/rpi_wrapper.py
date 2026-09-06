

class LedStrip:
    def __init__(self, testing=False, count=219, brightness=1.0):
        self.testing = testing

        if testing:
            self._strip = FakeLedStrip(count, brightness)
            return

        try:
            import board
            import neopixel
        except ImportError as error:
            raise RuntimeError(
                "NeoPixel hardware dependencies are required unless testing=True"
            ) from error

        self._strip = neopixel.NeoPixel(
            board.D10,
            count,
            brightness=brightness,
            auto_write=False,
        )

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

    def __setitem__(self, key, value):
        self._strip[key] = value

    def close(self):
        self.fill((0, 0, 0))
        self.show()

        close = getattr(self._strip, "deinit", None)
        if close is not None:
            close()

class FakeLedStrip:
    def __init__(self, count=219, brightness=1.0):
        self.count = count
        self.last_fill = None
        self.brightness = brightness

    def fill(self, color):
        self.last_fill = color

    def show(self):
        pass

    def __len__(self):
        return self.count

    def __setitem__(self, key, value):
        pass



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
