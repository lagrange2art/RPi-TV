import pytest
from rpitv.pixelmotion import Animation
from rpitv.rpi_wrapper import LedStrip
import time

@pytest.mark.parametrize("method", ["fire", "rotate", "strobo"])
def test_animation_start_stop(method):
    led_strip = LedStrip(testing=True, count=219, brightness=1.,)
    
    animation = Animation(led_strip) 
    animation.start(method)

    time.sleep(0.01)
    animation.stop()