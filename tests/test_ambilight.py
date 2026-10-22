import pytest
from rpitv.ambilight import Ambilight, get_boundary
from rpitv.rpi_wrapper import LedStrip
import numpy as np

def test_info():
    x = 4
    assert x == 4

def test_camera_resolution_setter_updates_capture_buffers():
    pixels = LedStrip(testing=True, count=219)
    ambilight = Ambilight(
        pixels=pixels,
        led_width=70,
        led_height=40,
        camera_resolution=(640, 480),
        offset=35,
    )

    ambilight.camera_resolution = "320x240"

    assert ambilight.camera_resolution == (320, 240)
    assert ambilight.video_buffer.shape == (240, 320, 3)
    assert ambilight._pixel_buffer_2d.shape == (40, 70, 3)
    assert ambilight.camera.closed


def test_ambilight_run_closes_camera_after_capture_error(monkeypatch, caplog):
    pixels = LedStrip(testing=True, count=40)
    ambilight = Ambilight(
        pixels=pixels,
        led_width=10,
        led_height=10,
        camera_resolution=(64, 48),
        offset=0,
    )

    class BrokenCamera:
        closed = False

        def capture_continuous(self, *_args, **_kwargs):
            raise RuntimeError("MMAL capture failure")

        def close(self):
            self.closed = True

    camera = BrokenCamera()
    monkeypatch.setattr("rpitv.ambilight.PiCamera", lambda *_resolution: camera)

    with pytest.raises(RuntimeError, match="MMAL capture failure"):
        ambilight.run()

    assert camera.closed
    assert "frame shape=(48, 64, 3)" in caplog.text
    assert "camera resolution=(64, 48)" in caplog.text

def test_ambilight_apply_mean_rgb():
    pixels = LedStrip(testing=True, count=219)
    
    ambilight = Ambilight(
            pixels=pixels,
            led_width = 71,
            led_height = 39,
            camera_resolution=(64,32),
            offset = 35, 
    )
    
    color = [255,100,10]
    ambilight.video_buffer[:,:, None] = color

    ambilight.apply_mean_rgb()
    output_color = np.dot(color, ambilight.calibration_matrix.T)

    for i in range(len(pixels)):
        assert np.allclose(pixels[i], output_color)

def test_ambilight_apply_edge_rgb():
    led_height, led_width = 10, 10
    # adjust resolution of camera to match exactly ambilight grid (no interpolation)
    pixels = LedStrip(testing=True, count=2*(led_height + led_width) )
    ambilight = Ambilight(
            pixels=pixels,
            led_width = led_width,
            led_height = led_height,
            camera_resolution=(led_width, led_height ),
            offset = 0, 
    )
    ambilight.calibration_matrix = np.eye(3)

    upper = [255,   0,   0]
    right = [  0, 255,   0]
    lower = [  0,   0, 255]
    left  = [255, 255, 255]

    # put color on edges of image
    ambilight.video_buffer[:] = [0,0,0]
    ambilight.video_buffer[0,1:, :] = [upper] * (ambilight.camera_resolution[0] - 1)
    ambilight.video_buffer[1:,-1, :] = [right] * (ambilight.camera_resolution[1] - 1)
    ambilight.video_buffer[-1,:-1, :] = [lower]* (ambilight.camera_resolution[0] - 1)
    ambilight.video_buffer[:-1,0, :] = [left]* (ambilight.camera_resolution[1] - 1)

    # apply edge color to led strip
    ambilight.apply_edge_rgb()
    # sanity check no image interpolation
    assert np.allclose(ambilight.video_buffer, ambilight._pixel_buffer_2d)

    # check colors of led match to image
    for index, pixel in enumerate(pixels):
        if index == 0:
            assert np.allclose(pixel, left)
        if 0 < index < led_width:
            assert np.allclose(pixel, upper)
        if led_width < index < (led_width + led_height):
            assert np.allclose(pixel, right)
        if (led_width + led_height) < index < (led_width + 2*led_height):
            assert np.allclose(pixel, lower)
        if (led_width + 2*led_height) < index < 2*(led_width + led_height):
            assert np.allclose(pixel, left)

def test_ambilight_capture_photo(tmp_path):
    led_height, led_width = 30, 70
    # adjust resolution of camera to match exactly ambilight grid (no interpolation)
    pixels = LedStrip(testing=True, count=2*(led_height + led_width) )
    ambilight = Ambilight(
            pixels=pixels,
            led_width = led_width,
            led_height = led_height,
            camera_resolution=(640, 490),
            offset = 0, 
    )

    ambilight.capture_photo(tmp_path / "test.png")

    assert (tmp_path / "test.png").exists()
    assert (tmp_path / "test_pixel_buffer.png").exists()

@pytest.mark.parametrize(
        "led_width, led_height",
        [
            (10, 10),
            (640,480),
            (64, 32),
            (7,9)
        ]
)
def test_get_boundary_length(led_width, led_height):

    image = np.ones((led_width, led_height))

    boundary = get_boundary(image.astype(bool))

    assert boundary.shape == (2*(led_width - 1 + led_height - 1), 2)

def test_get_boundary_square():

    led_width, led_height = 10, 10
    image = np.ones((led_width, led_height))

    start_angle = -np.pi/4
    boundary = get_boundary(image.astype(bool), start_angle)
    

    edge_top_right_bottom_left = np.array(
        [[0, i] for i in range(led_width - 1)] 
        + [[i, led_width - 1] for i in np.arange(led_height - 1)] 
        + [[led_height - 1, led_width - 1 - i] for i in range(led_width - 1)] 
        + [[led_height - 1 - i, 0] for i in range(led_height - 1)] 
    )

    assert np.sum(np.abs(boundary - edge_top_right_bottom_left)) < 1e-3

