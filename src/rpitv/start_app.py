""" https://projects.raspberrypi.org/en/projects/python-web-server-with-flask/1
this is run at startup using systemd. Created file /lib/systemd/system/rpitv.service
essentially with content python /home/pi/Documents/webapp/app.py. 
Then start service with: sudo systemctl start rpitv.service
If it works, then stop service: sudo systemctl stop rpitv.service
Enable service to run on startup: sudo systemctl enable rpitv.service
"""
import argparse
import numpy as np
from matplotlib.pyplot import get_cmap
from matplotlib import cm
from matplotlib.colors import Normalize


from flask import Flask, render_template, request
import threading 

from rpitv.pixelmotion import Rotate, Strobo
from rpitv.pixelaudio import AudioVisual



from rpitv.rpi_wrapper import (
    LedStrip,
    ADC,
    # FakeRotate,
    # FakeStrobo,
    # FakeAudioVisual,
)


class RPiTV:
    def __init__(self, app, brightness=0.5, testing: bool=False):
        self.app = app
        self.brightness = brightness

        adc = ADC(testing=testing)
        pixels = LedStrip(testing=testing)
        rotate = Rotate(pixels)
        strobo = Strobo(pixels)
        audiovisual = AudioVisual(adc, pixels)

        self.pixels = pixels
        self.adc = adc
        self.rotate = rotate
        self.strobo = strobo
        self.audiovisual = audiovisual

        self.add_endpoint('/', '', self.index, methods=['GET'])
        self.add_endpoint('/fillstrip/<rgb>', 'fillstrip', self.fillstrip, methods=['GET'])
        self.add_endpoint('/fillstrip/<rgb>', 'setbrightness', self.set_brightness, methods=['POST', 'GET'])
        self.add_endpoint('/animation/', 'animation', self.animation)
        self.add_endpoint('/animation/strobo/', 'strobo', self.strobo_mode)
        self.add_endpoint('/audiovisual/<method>', 'audiovisual', self.audiovis, methods=['GET'])

    def add_endpoint(self, endpoint=None, endpoint_name=None, handler=None, methods=['GET'], *args, **kwargs):
        self.app.add_url_rule(endpoint, endpoint_name, handler, methods=methods, *args, **kwargs)
    
    def run(self, **kwargs):
        self.app.run(**kwargs)
        

    def index(self):
        """ home screen of website. load content from template folder"""
        self.rotate.STOP_THREAD = True
        self.audiovisual.STOP_THREAD = True     
        self.strobo.STOP_THREAD = True
        return render_template('index.html')


    def fillstrip(self, rgb):
        """ When URL fillstrip/rgb is requested the led strip lights up
        according to rgb values. 
        param str rgb: string with comma seperated rgb values """
        # adjust brightness of rgb = 'r,g,b'
        rgb = np.array(rgb.split(',')).astype(int)   # rgb = [r,g,b]
        rgb = (self.brightness*rgb).astype(int)
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
            brightness=self.brightness,
        )


    def set_brightness(self, rgb):
        if request.method == 'GET':
            return "Use the brightness slider to update the value"

        self.brightness = float(request.form['Brightness'])
        return self.fillstrip(rgb)


    def animation(self):
        length = len(self.pixels)
        cmap = get_cmap('hsv')#'plasma')#viridis')#spring')#twilight')#
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
        print(type(method))
        thread = threading.Thread(target=self.audiovisual.run, args=(method,))
        self.audiovisual.STOP_THREAD = False
        thread.start()
        return render_template('audiovisual.html', name=method)

    def close(self):
            self.rotate.STOP_THREAD = True
            self.strobo.STOP_THREAD = True
            self.audiovisual.STOP_THREAD = True

            # for thread in self.threads:
            #     thread.join(timeout=2)

            self.adc.close()
            self.pixels.close()

def main(args=None) -> None:
    if args is None:
        parser = argparse.ArgumentParser()
        parser.add_argument('--port', type=int, default=5000)
        parser.add_argument('--testing', type=bool, default=False)

        args = parser.parse_args()

    rpitv = RPiTV(
        Flask(__name__),
        brightness=0.5,
        testing=args.testing,
    )
    try:
        rpitv.run(debug=False, host='0.0.0.0', port=args.port)
    finally:
        rpitv.close()

if __name__ == '__main__':

    main()

