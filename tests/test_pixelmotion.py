import pytest
from rpitv.pixelmotion import Rotate
from rpitv.rpi_wrapper import LedStrip
import threading
import time


def test_rotate():
    led_strip = LedStrip(testing=True, count=219, brightness=1.,)

    rotate = Rotate(led_strip)
    colors = [[255,255,0]] + [[0,0,0]]*(len(led_strip) - 1)
    thread = threading.Thread(target=rotate.run, args=(colors, -1))

    # rotate.STOP_THREAD = False
    thread.start()
    time.sleep(0.5)
    rotate.STOP_THREAD = True