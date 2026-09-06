""" first test with led strip. Test for led strip with 60 led. Chose a particular led and pick r,g,b values to light up the specific led. \n ctrl-c to exit program and turn off led strip \n"""



import sys
import threading

from rpitv.pixelmotion import fill_section  # has global variables: length and 

from rpitv.rpi_wrapper import (
    LedStrip,
    ADC,
)

import matplotlib as mpl
import matplotlib.pyplot as plt
from matplotlib import cm
import numpy as np

import time




class AudioVisual:
    def __init__(self, adc, pixels):
        #cdef int bright, length, noise, maxvol, maxled_old, value, maxled, i
        self.adc = adc
        self.pixels = pixels
        self.STOP_THREAD = False
        
    def run(self, method='ladder'):
        length = len(self.pixels)
        #cmap = plt.get_cmap('hsv')
        #norm = mpl.colors.Normalize(vmin=0, vmax=length)
        #scalarMap = cm.ScalarMappable(norm=norm, cmap=cmap)
        
        noise = 127    # no sound returns channel 127
        maxvol = 128

        sampsize = 100      # freq analyis finite number of vals     
        t = []
        signal = []
        for i in range(sampsize):
                    t.append(time.time())
                    signal.append(self.adc.analogRead(0))
        dt = (t[-1] - t[0])/sampsize     # times should be equidistant
        freq = np.fft.rfftfreq(sampsize, d=dt)   # get possible frequencies for signal
        maxled_old = 0
        while True:
            t = t[1:] + [time.time()]
            signal = signal[1:] + [self.adc.analogRead(0)]
            
            #fft_spectrum = np.fft.rfft(signal)       # fast fourier transform, population of frequencies in signal
    
            #value = adc.analogRead(0)    # read the ADC value 0 to 255
            #print(np.sum(fft_spectrum))
            
            
            if method == 'ladder':
                value = np.max(signal)
                perc = abs(value - noise)/maxvol  # relative loudness [0,1]
                maxled = int(perc*(length- 1))
                
                if maxled < maxled_old:
                    # turn off all leds higher than old
                    fill_section(self.pixels, maxled, maxled_old + 1, [0,0,0])    
                
                elif maxled > maxled_old:
                    fill_section(self.pixels, maxled_old, maxled, [127,76,25])
                    # rgb_norm = scalarMap.to_rgba(i)[:3]
                    # pixels[i] = (rgb_norm[0], rgb_norm[1], rgb_norm[2])
                
                maxled_old = maxled
                
            elif method == 'pulse':
                perc = np.max(np.abs(np.array(signal)[-5:] - noise)/maxvol)
                self.pixels.fill([int(perc*255), int(perc*255), int(perc*255)])
                self.pixels.show()

            if self.STOP_THREAD:
                self.pixels.fill((0,0,0))
                self.pixels.show()
                break
            
            
def audiopulse(adc, pixels):
    color = np.array([0.8,0.1,0.1]) 

    
    noise = 127    # no sound returns channel 127
    maxvol = 128

    while True:
        try:      
            value = adc.analogRead(0)    # read the ADC value 0 to 255
            perc = abs(value - noise)/maxvol  # relative loudness [0,1]
            
            bright = 0
            if perc > 0.1:
                bright = perc*255
            
            pixels.fill(bright*color)
            

        except KeyboardInterrupt:
            pixels.fill((0,0,0))
            return 0

def claponoff(adc, pixels):
    threshold = 0.2
    bright = [0,10,100,255]
    
    noise, maxvol = 127, 128
    color = np.array([0.8,0.1,0.1]) 
    i = 0
    while True:
        try:      
            value = adc.analogRead(0)         # read the ADC value 0 to 255
            perc = abs(value - noise)/maxvol  # relative loudness [0,1]
    
            if perc > threshold:
                
                pixels.fill(bright[i%len(bright)]*color)
                
                time.sleep(0.1)
                i += 1

        except KeyboardInterrupt:
            pixels.fill((0,0,0))
            return 0
    

def main(testing):
    adc = ADC(testing)
  
    #freq = 800000
    #led_dma = 5
    #invert = True
    #brightness = 255
    
    pixels = LedStrip(testing=testing)
    method = 'pulse' #
    #method = 'ladder'# 
    audiovisual = AudioVisual(adc, pixels)
    thread = threading.Thread(target=audiovisual.run, args=(method,))
    audiovisual.STOP_THREAD = False

    thread.start()
    input('enter to stop')
    audiovisual.STOP_THREAD = True
    
    #audiopulse(adc,pixels)
    #claponoff(adc,pixels)


if __name__ == '__main__':
        print(__doc__)
        main(testing=True)
        
        
        
