""" Animation for led strip on D10. """

import logging

from rpitv.rpi_wrapper import LedStrip
import threading 


from matplotlib.pyplot import get_cmap
from matplotlib import cm
from matplotlib.colors import Normalize
import numpy as np

import time


logger = logging.getLogger(__name__)


class Rotate:
    """ rotate a given led picture. colors is a 2d array of rgb values for each led. In each iteration move rgb values and update pixels. step specifies how far the values are moved to the left """    
    def __init__(self, pixels):
        """ rotate a given led picture. colors is a 2d array of rgb values for each led. In each iteration move rgb values and update pixels. step specifies how far the values are moved to the left """    
        self.pixels = pixels
        self.STOP_THREAD = False
    
    def run(self, colors, step=1):
        
        self.pixels[:] = colors
        self.pixels.show()
        colors_new = colors
        while True:
            #colors = np.vstack((colors[-step:,:], colors[:-step,:]))
            colors_new[:step,:] = colors[-step:,:]
            colors_new[step:,:] = colors[:-step,:]
            colors = colors_new
            self.pixels[:] = colors
            self.pixels.show()
            
            if self.STOP_THREAD:
                logger.info('Turning off LEDs after rotation')
                self.pixels.fill((0,0,0))
                self.pixels.show()
                break
        

def animation():
    """ move leds in rythm of music"""
   
    length = 219
  
    brightness = 1
    pixels = LedStrip(count=length, brightness=brightness)
    

    cmap = get_cmap('plasma')#viridis')#spring')#twilight')#'hsv')
    norm = Normalize(vmin=0, vmax=length)
    scalarMap = cm.ScalarMappable(norm=norm, cmap=cmap)
    colors = ((scalarMap.to_rgba(np.arange(length))*255)[:,:3]).astype(int)    

    rotate = Rotate(pixels) 
    thread = threading.Thread(target=rotate.run, args=(colors, -10))
    thread.start()
    
    
    input('enter to stop')
    rotate.STOP_THREAD = True
    print(rotate.STOP_THREAD)

class Strobo:
    def __init__(self, pixels):
        """ rotate a given led picture. colors is a 2d array of rgb values for each led. In each iteration move rgb values and update pixels. step specifies how far the values are moved to the left """    
        self.pixels = pixels
        self.STOP_THREAD = False
    
    def run(self, color=[255,255,255]):
        start = time.time()
        i = 0   # count flashes, there should be 10-12 per second for strobo effect
        while True:
            #time.sleep(0.5)
            self.pixels.fill(color)
            self.pixels.show()
            time.sleep(0.01)
            self.pixels.fill((0,0,0))
            self.pixels.show()
            time.sleep(0.03)
            i += 1
            if self.STOP_THREAD:
                logger.info('Turning off LEDs after strobe')
                self.pixels.fill((0,0,0))
                self.pixels.show()
                logger.info('%d flashes in %.2f sec', i, time.time() - start)
                break
        
def animate_strobo():
    """ move leds in rythm of music"""
    length = 219
    brightness = 1
    pixels = neopixel.NeoPixel(board.D10, length, brightness=brightness, auto_write=False)

    strobo = Strobo(pixels) 
    thread = threading.Thread(target=strobo.run)
    thread.start()
    
    input('enter to stop')
    strobo.STOP_THREAD = True


def fill_section(pixels, start=0, stop=219, rgb_list=[0,0,0]):
    """fill section of led strip with selected rgb values. if just one rgb value is given, then light up leds in this
    single color.
    either: rgb_list=[[r1,g1,b1], [r2,g2,b2],...] or rgb_list=[r,g,b]
    """
    numled = stop - start
    if type(rgb_list[0]) == list:    
        if len(rgb_list) <= numled:
            missing = numled - len(rgb_list)
            rgb_list += [[0,0,0]] * missing    # fill missing rgb values and turn them off
    elif type(rgb_list[0]) == int:
        rgb_list = [rgb_list] * numled   # if just obe rgb tuple given, light leds in this single 
    else:
        raise ValueError('unknown rgb_list fornat')

    pixels[start:stop] = rgb_list
    pixels.show()


def main():      
    #animation()
    animate_strobo()

if __name__ == '__main__':
        print(__doc__)
        main()
        
        
        
