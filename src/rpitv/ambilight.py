""" Ambilight: Light led strip accroding to TV screen. 
Record TV-screen with raspberry pi camera. Find rgb-values of boundary 
and light up led strip with this rgb values. To this end attach led strip 
on the back of the TV. For a good result make sure that the boundary of 
the camera capture is aligned with the screens boundary. 
Connect ledstrip to raspberry pi GPIO 18

Copyright: Tobias Becker
""" 
from rpitv.rpi_wrapper import (
    LedStrip,
    PiCamera,
    FakePiCamera,
)
import logging
import numpy as np
from cv2 import resize # from skimage.transform import resize
import cv2
from pathlib import Path
import time

logger = logging.getLogger(__name__)


class Ambilight(object):
    
    def __init__(
            self,
            pixels:LedStrip,
            camera_resolution:tuple,
            led_width:int,
            led_height:int,
            offset:int,
        ):
        """
        capture video via picamera and store rgb values to array with given resolution. For a fast capture use video port. 
        Then loop over the top row, right, bottom and left of the ambilight led strip one after another. To find rgb value 
        for each led make some average that fits to the number of leds in horizontal and vertical direction.
        :param cam: PiCamera object
        :param pixels: instance of neopixel to controll led strip
        :param led_width: number of leds in x-direction
        :param led_height: number of leds in y-direction
        :offset: strip starts in top row, but in the middle with offset leds before it
        """
        self.blind_pixels = 2*(led_width + led_height) - len(pixels)

        if self.blind_pixels > 0:
            logger.warning(f"led (width,height) '{led_width}x{led_height}' does not fit to length of LedStrip({len(pixels)})")

        self.led_width = led_width    # number of leds in x-direction
        self.led_height = led_height   # number of leds in y-direction
        self.offset = offset       # strip starts in top row, but in the middle with offset leds before it

        self.pixels = pixels 
        self._initialize_pixel_buffers()

        self.camera = FakePiCamera()
        # self.camera.closed = True  # force to open a new instance 
        self.camera_resolution = camera_resolution


        self.calibration_matrix = get_calibration_matrix(method="constraints")
    
        self.STOP_THREAD = False

    def _initialize_pixel_buffers(self,):
        self._pixel_buffer_2d = np.empty(
            (self.led_height, self.led_width, 3),
            dtype=np.uint8,
        )
        # edge indices of pixel_buffer edge that are streamed to led strip
        self._pixel_buffer_2d_edge = np.array(
            [[i,0] for i in range(self.led_width)] 
            + [[self.led_width-1,i] for i in range(self.led_height)] 
            + [[i, self.led_height-1] for i in range(self.led_width)[::-1]] 
            + [[0,i] for i in range(self.led_height)[::-1]] 
        )


    @property
    def camera_resolution(self):
        return self._camera_resolution
    
    @camera_resolution.setter
    def camera_resolution(self, value):
        """Set camera dimensions and recreate buffers before the next capture."""
        if isinstance(value, str):
            parts = value.lower().split("x")
            if len(parts) != 2:
                raise ValueError("Camera resolution must be formatted as WIDTHxHEIGHT")
        elif isinstance(value, (tuple, list)) and len(value) == 2:
            parts = value
        else:
            raise ValueError("Camera resolution must be a WIDTHxHEIGHT string or a pair")

        try:
            resolution = tuple(int(dimension) for dimension in parts)
        except (TypeError, ValueError) as exc:
            raise ValueError("Camera resolution dimensions must be integers") from exc

        if any(dimension <= 0 for dimension in resolution):
            raise ValueError("Camera resolution dimensions must be positive")

        if getattr(self, "_camera_resolution", None) == resolution:
            return

        self.camera.close()
        self._camera_resolution = resolution
        self.video_buffer = np.empty(
            (resolution[1], resolution[0], 3),
            dtype=np.uint8,
        )




    def calibrate_rgb(self, rgb):
        return np.dot(rgb, self.calibration_matrix.T)
        rgb = np.asarray(rgb, dtype=np.float32)

        corrected = np.maximum(rgb, 0)
        corrected *= np.asarray(gains)

        corrected = np.clip(corrected / 255.0, 0.0, 1.0)
        corrected = corrected ** gamma

        return np.rint(corrected * 255).astype(np.uint8)   

    def apply_mean_rgb(self) -> None:
        """ Light up leds according to mean rgb of captured image """
        mean_color = np.mean(self.video_buffer, axis=(0,1), dtype=int)   # take mean rgb over x-y plane
        self.pixels.fill(self.calibrate_rgb(mean_color))

    def apply_edge_rgb(self) -> None:
        """ Light up leds according to the edge of the captured image """
        
        resize(
            src=self.video_buffer,
            dsize=self._pixel_buffer_2d.shape[1::-1],
            dst=self._pixel_buffer_2d,
        )

        # take edge --> remove led offset --> calibrate rgb values --> update pixel
        self.pixels[:] = self.calibrate_rgb(
            np.roll(
                self._pixel_buffer_2d[self._pixel_buffer_2d_edge[:,1], self._pixel_buffer_2d_edge[:,0]], 
                shift=-self.offset, 
                axis=0
            )
        )[self.blind_pixels:]

    def run(self, method:str="apply_edge_rgb"):
        logger.info('start ambilight')
        camera = None
        try:
            if self.camera.closed:
                self.camera = PiCamera(*self.camera_resolution)
            camera = self.camera

            if method == "apply_mean_rgb":
                logger.info("run apply_mean_rgb")
                method_func = self.apply_mean_rgb
            else:
                logger.info("run apply_edge_rgb")
                method_func = self.apply_edge_rgb

            # Set up method_func, then run the existing capture loop.
            for _ in camera.capture_continuous(
                self.video_buffer,
                format="rgb",
                use_video_port=True,
            ):
                method_func()
                self.pixels.show()

                if self.STOP_THREAD:
                    break

        except Exception:
            logger.exception(
                "Ambilight run failed: frame shape=%s, camera resolution=%s",
                self.video_buffer.shape,
                self.camera_resolution,
            )
            raise

        finally:
            logger.info("Close Ambilight")
            if camera is not None:
                try:
                    camera.close()
                except Exception:
                    logger.exception("Failed to close Ambilight camera")
            try:
                self.pixels.fill((0, 0, 0))
                self.pixels.show()
                time.sleep(0.05)  # Allow the Arduino time to process the frame
            except Exception:
                logger.exception("Failed to clear pixels after Ambilight stopped")

    def capture_photo(self, outpath:Path=Path(__file__).parent / "static" / "ambilight_capture.png"):
        from matplotlib.image import imsave

        if not self.camera.closed:
             self.STOP_THREAD = True

        while True:
            # wait for closing of camera module first
            camera = None
            if self.camera.closed:
                try:
                    camera = PiCamera(*self.camera_resolution)
                    # camera.capture(str(outpath))#, use_video_port=True)

                    # take second photo to video_buffer
                    camera.capture(self.video_buffer, format="rgb")
                    imsave(
                            str(outpath), 
                            self.video_buffer,
                    )
                    resized_photo = resize(
                        src=self.video_buffer,
                        dsize=self._pixel_buffer_2d.shape[1::-1],
                    )
                    resized_photo[self._pixel_buffer_2d_edge[:,1], self._pixel_buffer_2d_edge[:,0]] = [255,255,255]
                    imsave(
                        str(outpath).replace(".png", "_pixel_buffer.png"), 
                        resized_photo,
                    )
                    
                    logger.info(f"Picture saved to {str(outpath)}")

                
                finally:
                    if camera is not None:
                        try:
                            camera.close()
                        except Exception:
                            logger.exception("Failed to close Ambilight camera")

                    return outpath

    def video_stream(self):
        logger.info('start video stream')
        self.pixels.fill((0,0,0))
        self.pixels.show()

        if self.camera.closed:
             self.camera = PiCamera(*self.camera_resolution)

        video_stream_color_format = "bgr"
        
        try: 
            for _ in self.camera.capture_continuous(self.video_buffer, format=video_stream_color_format, use_video_port=True):

                ok, jpeg = cv2.imencode(".jpg", self.video_buffer)
                if ok:
                    yield (
                        b"--frame\r\n"
                        b"Content-Type: image/jpeg\r\n\r\n"
                        + jpeg.tobytes()
                        + b"\r\n"
                    )
                time.sleep(0.03)            
                if self.STOP_THREAD:

                    break
        finally:
            logger.info("Close Ambilight")
            self.pixels.fill((0,0,0))
            self.pixels.show()
            self.camera.close()     


def get_calibration_matrix(
        method="constraints"
    ) -> np.ndarray:
    from scipy.optimize import minimize

    # mapping of measured input rgb values to desired output rgb values
    rgb_in = 1/255 * np.array(
        [
            [233,   9,  28], # measured red            
            [  0, 233,  80], # measured green
            [  0, 100, 245], # measured blue
            [210, 220, 210], # measured white
        ]
    )
    rgb_out = 1/255 * np.array(
        [
            [255,  15,   0], # --> red
            [128, 255,   0], # --> green            
            [ 20,   0, 255], # --> blue
            [255, 255, 255], # --> white
        ]
    )
    if method == "constraints":
        def objective(trafo_flat):
            trafo = trafo_flat.reshape((3, 3))
            # Berechnet die Vorhersage: Y = X * M^T
            Y_pred = np.dot(rgb_in, trafo.T)
            # Ziel: Summe der quadratischen Abweichungen minimieren
            return np.sum((rgb_out - Y_pred) ** 2)

        # Bedingung: Zeilensummen müssen <= 1.0 sein
        def row_sum_constraint(trafo_flat):
            trafo = trafo_flat.reshape((3, 3))
            return 1.0 - np.sum(trafo, axis=1) # Muss >= 0 sein für den Solver

        # Grenzen: Jeder Koeffizient muss zwischen 0.0 und 1.0 liegen
        bounds = [(0.0, 1.0) for _ in range(9)]
        constraints = {'type': 'ineq', 'fun': row_sum_constraint}

        # optimization with initial value given by identity trafo 
        init = np.eye(3).flatten()

        # Optimierung ausführen
        res = minimize(objective, init, bounds=bounds, constraints=constraints)
        calibration_matrix = res.x.reshape((3, 3))

    elif method == "no_constraints":
        # Solve for the best-fitting 3x3 matrix (Least Squares)
        # Y_out = X_in * M^T  -->  M^T = pinv(X_in) * Y_out
        calibration_matrix_T, _residuals, _rank, _s = np.linalg.lstsq(rgb_in, rgb_out, rcond=None)
        calibration_matrix = calibration_matrix_T.T

    elif method == "exact_map":
        calibration_matrix = rgb_out[:-1,:].T @ np.linalg.inv(rgb_in[:-1,:].T)

    else:
        logger.warning('no calibration method given use identity')
        calibration_matrix = np.eye(3)

    return calibration_matrix


def get_boundary(
        image: np.ndarray,
        start_angle = 0., 
    ) -> np.ndarray:
    """ Return boundary indices of 2d boolean array"""
    if not len(image.shape) == 2:
        raise ValueError("Image must be a 2d array")
    image_bool = image.copy().astype(bool)
    
    # 1. Identify all edge pixels using vectorized grid shifting
    # An edge pixel is True but touches at least one False neighbor
    shifted_up = np.roll(image_bool, -1, axis=0); shifted_up[-1, :] = False
    shifted_down = np.roll(image_bool, 1, axis=0); shifted_down[0, :] = False
    shifted_left = np.roll(image_bool, -1, axis=1); shifted_left[:, -1] = False
    shifted_right = np.roll(image_bool, 1, axis=1); shifted_right[:, 0] = False
    
    has_false_neighbor = (~shifted_up | ~shifted_down | ~shifted_left | ~shifted_right)
    edge_mask = image_bool & has_false_neighbor
    
    # 2. Extract coordinates of the boundary pixels
    rows, cols = np.where(edge_mask)
    if len(rows) == 0:
        print("no boundary found")
        return np.empty((0, 2), dtype=int)
    points = np.column_stack((rows, cols))
    
    # 3. Vectorized Sorting by Polar Angle (No loops)
    # Calculate the center of mass (centroid) of the boundary
    center_row = np.mean(rows)
    center_col = np.mean(cols)
    
    # Zero points up; angles increase clockwise in image coordinates.
    angles = np.mod(
        np.arctan2(cols - center_col, center_row - rows) - start_angle,
        2 * np.pi,
    )
    # Sort the points based on their angles to form a continuous path
    sort_indices = np.argsort(angles)
    ordered_points = points[sort_indices]
    
    # # 4. Explicitly close the curve by appending the first point to the end
    # closed_curve = np.vstack([ordered_points, ordered_points[0]])
    
    return ordered_points

def main():
    """ specify number of leds, create PiCamera/neopixel instances and run Ambilight()"""    
    led_width = 71    # number of leds in x-direction
    led_height = 39   # number of leds in y-direction
    offset = 35       # strip starts in top row, but in the middle with offset leds before it
    pixels = LedStrip(testing=True, brightness=1.0, hardware="rpi")
    amblight = Ambilight(pixels, led_width, led_height, (128,96), offset)
    amblight.run()

if __name__ == '__main__':
        print(__doc__)
        main()

