import pytest
from rpitv.rpi_wrapper import FakeLedStrip, LedStrip


def test_led_strip():
    count = 10
    brightness = 0.5
    strip = LedStrip(testing=True, count=count, brightness=brightness)

    assert len(strip) == count
    assert strip.brightness == brightness

    # Test setting and getting pixel values
    for i in range(count):
        color = (i * 10, i * 20, i * 30)
        strip[i] = color
        assert strip[i] == color

    # Test fill method
    fill_color = (100, 150, 200)
    strip.fill(fill_color)
    for i in range(count):
        assert strip[i] == fill_color

    # test setting brightness
    new_brightness = 0.8
    strip.brightness = new_brightness
    assert strip.brightness == new_brightness

    # Test show method (should not raise any exceptions)
    strip.show()
