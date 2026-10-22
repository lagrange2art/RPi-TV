#!/usr/bin/env python
""" https://projects.raspberrypi.org/en/projects/python-web-server-with-flask/1
this is run at startup using systemd. Created file /lib/systemd/system/rpitv.service
essentially with content python /home/pi/Documents/webapp/app.py. 
Then start service with: sudo systemctl start rpitv.service
If it works, then stop service: sudo systemctl stop rpitv.service
Enable service to run on startup: sudo systemctl enable rpitv.service
"""
import argparse
import logging
import os
import signal
import numpy as np
from matplotlib.pyplot import get_cmap
from matplotlib import cm
from matplotlib.colors import Normalize


from flask import Flask, Response, render_template, request
import threading 
import time
from rpitv.pixelmotion import Rotate, Strobo
from rpitv.pixelaudio import AudioVisual
from rpitv.logger import (
    LOG_PATH,
    ansi_to_html,
    configure_logging,
)

from rpitv.rpi_wrapper import (
    LedStrip,
    ADC,
    PiCamera,
    # FakeRotate,
    # FakeStrobo,
    # FakeAudioVisual,
)
from rpitv.ambilight import Ambilight

logger = logging.getLogger(__name__)
CAMERA_RESOLUTIONS = {
    "2592x1944": (2592, 1944), # too much for rpi2 ? 
    "1296x972": (1296, 972),
    "690x720": (690, 720),
    "640x480": (640, 480),
    "480x270": (480,270),
    "320x240": (320, 240),
    "160x90": (160, 90),
    "64x64": (64, 64),
    "64x48": (64, 48),
    "32x16": (32,16),
}


class RPiTV:
    def __init__(self, app, brightness=0.5, testing: bool=False, hardware: str = "rpi"):
        self.app = app
        try:
            adc = ADC(testing=testing)
        except RuntimeError as e:
            logger.error("Failed to initialize ADC: %s", e)
            adc = ADC(testing=True)  # Fallback to testing mode if ADC initialization fails

        pixels = LedStrip(testing=testing, brightness=brightness, hardware=hardware)
        rotate = Rotate(pixels)
        strobo = Strobo(pixels)
        audiovisual = AudioVisual(adc, pixels)

        self.pixels = pixels
        self.adc = adc
        self.rotate = rotate
        self.strobo = strobo
        self.audiovisual = audiovisual
        self._closed = False
        self.ambilight_thread = None
        self.ambilight_mode = "apply_edge_rgb"
        
        self.ambilight = Ambilight(
            pixels=pixels,
            led_width = 71,
            led_height = 39,
            camera_resolution=(640,480),#(2592,1944),#(96,48),
            offset = 35, 
        )
        self.add_endpoint('/', '', self.index, methods=['GET'])
        self.add_endpoint('/restart', 'restart_server', self.restart_server, methods=['POST'])
        self.add_endpoint('/fillstrip/<rgb>', 'fillstrip', self.fillstrip, methods=['GET'])
        self.add_endpoint('/fillstrip/<rgb>', 'setbrightness', self.set_brightness, methods=['POST', 'GET'])
        self.add_endpoint('/animation/', 'animation', self.animation)
        self.add_endpoint('/animation/strobo/', 'strobo', self.strobo_mode)
        self.add_endpoint('/audiovisual/<method>', 'audiovisual', self.audiovis, methods=['GET'])
        self.add_endpoint(
            '/ambilight/',
            'ambilight',
            self.run_ambilight,
            methods=['GET']
        )
        self.add_endpoint(
            '/ambilight/capture_photo/',
            'capture_photo',
            self.capture_photo,methods=['GET']
        )
        self.add_endpoint(
            "/ambilight/video/",
            "ambilight_video_page",
            self.ambilight_video_page,
        )
        self.add_endpoint(
            "/ambilight/video_stream/",
            "video_stream",
            self.video_stream,
        )

        self.add_endpoint('/logs', 'logs', self.logs, methods=['GET'])
        self.add_endpoint('/logs/benchmark/', 'benchmark', self.benchmark)

    def add_endpoint(self, endpoint=None, endpoint_name=None, handler=None, methods=['GET'], *args, **kwargs):
        self.app.add_url_rule(endpoint, endpoint_name, handler, methods=methods, *args, **kwargs)
    
    def run(self, **kwargs):
        self.app.run(**kwargs)

    def restart_server(self):
        logger.info("Server restart requested")

        def terminate_process():
            os.kill(os.getpid(), signal.SIGTERM)

        restart_timer = threading.Timer(1.0, terminate_process)
        restart_timer.daemon = True
        restart_timer.start()
        return "Restarting the server...", 202
        

    def index(self):
        """ home screen of website. load content from template folder"""
        thread = self.ambilight_thread
        if thread is not None and thread.is_alive():
            self.ambilight.STOP_THREAD = True
            thread.join(timeout=5)
            if thread.is_alive():
                err_msg = "Ambilight thread did not stop"
                logger.error(err_msg)
                return err_msg, 503

        self.ambilight_thread = None
        self.rotate.STOP_THREAD = True
        self.audiovisual.STOP_THREAD = True     
        self.strobo.STOP_THREAD = True
        return render_template('index.html')


    def fillstrip(self, rgb):
        """ When URL fillstrip/rgb is requested the led strip lights up
        according to rgb values. 
        param str rgb: string with comma seperated rgb values """
        rgb = np.array(rgb.split(',')).astype(int)   # rgb = [r,g,b]
        rgb = ','.join(rgb.astype(str))              # rgb = 'r,g,b'

        if isinstance(rgb, str):
            rgbvals = np.array(rgb.split(',')).astype(int)
        else:
            rgbvals = rgb
        self.pixels.fill((rgbvals[0], rgbvals[1], rgbvals[2]))
        self.pixels.show()

        return render_template(
            'fillstrip.html',
            name=rgb,
            brightness=self.pixels.brightness,
        )


    def set_brightness(self, rgb):
        if request.method == 'GET':
            return "Use the brightness slider to update the value"

        self.pixels.brightness = float(request.form['Brightness'])
        return self.fillstrip(rgb)


    def animation(self, cmap_name='hsv'):
        length = len(self.pixels)
        cmap = get_cmap(cmap_name)#'plasma')#viridis')#spring')#twilight')#
        norm = Normalize(vmin=0, vmax=length)
        scalarMap = cm.ScalarMappable(norm=norm, cmap=cmap)
        colors = ((scalarMap.to_rgba(np.arange(length))*255)[:,:3]).astype(int)      

        thread = threading.Thread(target=self.rotate.run, args=(colors, -1))
        self.strobo.STOP_THREAD = True
        self.rotate.STOP_THREAD = False
        thread.start()
        return render_template('animation.html')

    def strobo_mode(self):
        thread = threading.Thread(target=self.strobo.run)
        self.rotate.STOP_THREAD = True
        self.strobo.STOP_THREAD = False
        thread.start()
        return render_template('animation.html')

    def audiovis(self, method='ladder'):
        logger.info("Starting audiovisual mode: %s", method)
        thread = threading.Thread(target=self.audiovisual.run, args=(method,))
        self.audiovisual.STOP_THREAD = False
        thread.start()
        return render_template('audiovisual.html', name=method)

    def run_ambilight(self):
        ambilight_mode = request.args.get("method", default="apply_edge_rgb")
        if ambilight_mode not in {"apply_mean_rgb", "apply_edge_rgb"}:
            err_msg = "Unsupported Ambilight method"
            logger.error(err_msg)
            return err_msg, 400

        current_resolution = self.ambilight.camera_resolution
        current_resolution_value = f"{current_resolution[0]}x{current_resolution[1]}"
        camera_resolution_value = request.args.get(
            "camera_resolution",
            default=current_resolution_value,
        )
        if camera_resolution_value not in CAMERA_RESOLUTIONS:
            return "Unsupported camera resolution", 400

        camera_resolution = CAMERA_RESOLUTIONS[camera_resolution_value]
        thread = self.ambilight_thread
        settings_changed = (
            ambilight_mode != self.ambilight_mode
            or camera_resolution != current_resolution
        )
        if thread is not None and thread.is_alive():
            if settings_changed:
                logger.info(f"Ambilight settings: \nresolution:{camera_resolution_value} mode:{ambilight_mode}")
                self.ambilight.STOP_THREAD = True
                thread.join(timeout=5)
                if thread.is_alive():
                    return "Ambilight capture did not stop", 503
            else:
                return render_template(
                    "ambilight.html",
                    method=ambilight_mode,
                    camera_resolution=camera_resolution_value,
                    camera_resolutions=CAMERA_RESOLUTIONS,
                )

        if camera_resolution != current_resolution:
            logger.info(
                "Change camera resolution %s -> %s",
                current_resolution,
                camera_resolution,
            )
            self.ambilight.camera_resolution = camera_resolution

        self.ambilight.STOP_THREAD = False
        self.ambilight_mode = ambilight_mode
        self.ambilight_thread = threading.Thread(
            target=self.ambilight.run,
            args=(ambilight_mode,),
            daemon=True,
        )
        self.ambilight_thread.start()
        return render_template(
            "ambilight.html",
            method=ambilight_mode,
            camera_resolution=camera_resolution_value,
            camera_resolutions=CAMERA_RESOLUTIONS,
        )
    
    def capture_photo(self,):
        outpath = self.ambilight.capture_photo()
        return render_template(
            "ambilight.html",
            image_filename=outpath.name,
            image_version=outpath.stat().st_mtime_ns,
            method=self.ambilight_mode,
            camera_resolution=(
                f"{self.ambilight.camera_resolution[0]}x"
                f"{self.ambilight.camera_resolution[1]}"
            ),
            camera_resolutions=CAMERA_RESOLUTIONS,
        )
    
    def ambilight_video_page(self):
        """ render static html for video stream"""
        return render_template(
            "ambilight.html",
            show_video=True,
            method=self.ambilight_mode,
            camera_resolution=(
                f"{self.ambilight.camera_resolution[0]}x"
                f"{self.ambilight.camera_resolution[1]}"
            ),
            camera_resolutions=CAMERA_RESOLUTIONS,
        )

    def video_stream(self,):
        # stop ambilight thread and wait befor starting a new one
        self.ambilight.STOP_THREAD = True
        thread = self.ambilight_thread
        if thread is not None and thread.is_alive():
            thread.join(timeout=5)
            if thread.is_alive():
                err_msg = "Ambilight thread did not stop"
                logger.error(err_msg)
                return err_msg, 503

        self.ambilight_thread = None
        self.ambilight.STOP_THREAD = False
        return Response(
            self.ambilight.video_stream(),
            mimetype="multipart/x-mixed-replace; boundary=frame",
        )


    def logs(self):
        log_content = LOG_PATH.read_text() if LOG_PATH.exists() else "No log entries yet."
        return render_template('logs.html', log_content=ansi_to_html(log_content))

    def benchmark(self):
        """ benchmark the led strip by running a simple animation and measuring the time taken """
        iterations = 1000
        start_time = time.time()
        for _ in range(iterations):
            self.pixels.fill((0, 0, 0))
            self.pixels.show()

        elapsed_time = time.time() - start_time
        logger.info(f'Benchmark completed {iterations} animations in {elapsed_time:.2f} sec ==> {elapsed_time/iterations/len(self.pixels)*1000:.5f} milliseconds/(led * animation)')
        log_content = LOG_PATH.read_text() if LOG_PATH.exists() else "No log entries yet."
        return render_template('logs.html', log_content=ansi_to_html(log_content))

    def close(self):
        if self._closed:
            return

        self._closed = True
        logger.info("Closing rpitv")
        self.rotate.STOP_THREAD = True
        self.strobo.STOP_THREAD = True
        self.audiovisual.STOP_THREAD = True
        self.ambilight.STOP_THREAD = True
        self.adc.close()
        self.pixels.close()


def main(args=None) -> None:
    if args is None:
        parser = argparse.ArgumentParser()
        parser.add_argument('--port', type=int, default=5000)
        parser.add_argument('--hardware', default="arduino", choices=['rpi', 'arduino'], help='Specify the hardware to use: rpi or arduino')
        parser.add_argument('--testing', action='store_true')

        args = parser.parse_args()

    configure_logging()
    logger.info("Starting rpitv on port %s", args.port)

    rpitv = RPiTV(
        Flask(__name__),
        brightness=0.5,
        hardware=args.hardware,
        testing=args.testing,
    )

    def handle_shutdown(signum, frame):
        logger.info("Received shutdown signal %s", signum)
        rpitv.close()
        raise SystemExit(0)

    signal.signal(signal.SIGTERM, handle_shutdown)
    signal.signal(signal.SIGINT, handle_shutdown)

    try:
        rpitv.run(debug=False, host='0.0.0.0', port=args.port)
    finally:
        rpitv.close()

if __name__ == '__main__':

    main()

