import pytest
from rpitv.rpi_wrapper import FakeLedStrip, LedStrip, _configure_camera
import numpy as np

@pytest.mark.parametrize("hardware", [
    "testing",
    # "arduino",
])
def test_led_strip(hardware):
    count = 10
    brightness = 0.5
    if hardware == "testing":
        strip = LedStrip(testing=True, count=count, brightness=brightness)

    else:
        strip = LedStrip(testing=False, count=count, brightness=brightness, hardware=hardware)

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


@pytest.mark.parametrize("hardware", [
    "testing",
    # "arduino",
])
def test_led_strip_slicing(hardware:str):
    count = 10
    brightness = 0.5

    if hardware == "testing":
        strip = LedStrip(testing=True, count=count, brightness=brightness)

    else:
        strip = LedStrip(testing=False, count=count, brightness=brightness, hardware=hardware)

     # test slicing
    colors = [[255,0,0],[255,0,255],[255,255,0]]
    colors = np.array(colors + [[0,0,0]]*(count - 3))   
    assert len(colors) == len(strip)
    strip[:] = colors

    # Test show method (should not raise any exceptions)
    strip.show()

def test_arduino_strip_too_many_values_to_unpack():
    count = 219
    values = 220
    strip = LedStrip(testing=True, count=count, hardware="arduino")

    colors = [[0,0,0]]*(values)
    with pytest.raises(IndexError) as error:
        strip[:] = colors
        strip.show()
    assert f"Cannot set {values} rgb values to strip of length {count}" in str(error) 


def test_configure_camera_closes_device_when_configuration_fails():
    class BrokenCamera:
        closed = False
        exposure_speed = 1
        awb_gains = (1, 1)

        @property
        def resolution(self):
            return None

        @resolution.setter
        def resolution(self, _value):
            raise RuntimeError("MMAL camera setup failed")

        def close(self):
            self.closed = True

    camera = BrokenCamera()
    with pytest.raises(RuntimeError, match="MMAL camera setup failed"):
        _configure_camera(camera, 640, 480)

    assert camera.closed