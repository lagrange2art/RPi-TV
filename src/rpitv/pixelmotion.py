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

class Animation:
    def __init__(self, pixels: LedStrip):
        self.pixels = pixels
        self._stop_event = threading.Event()
        self._thread = None
        self._thread_lock = threading.RLock()
    
    def start(self, method, **kwargs):
        if method not in {"fire", "rotate", "strobo"}:
            raise ValueError(f"Unknown animation method: {method}")
    
        with self._thread_lock:
            self._stop_locked()
            self._stop_event.clear()
            self._thread = threading.Thread(
                target=self.run,
                args=(method,),
                kwargs=kwargs,
                daemon=True,
            )
            self._thread.start()
    
    def stop(self, timeout=5):
        with self._thread_lock:
            self._stop_locked(timeout)
    
    def _stop_locked(self, timeout=5):
        thread = self._thread
        if thread is None:
            return
    
        self._stop_event.set()
        if thread is threading.current_thread():
            return
    
        thread.join(timeout)
        if thread.is_alive():
            raise RuntimeError("Animation thread did not stop")
    
        self._thread = None


    def run(self, method:str, **kwargs):
        if method == 'fire':
            self._simulate_fire(**kwargs)

        elif method == 'rotate':
            self._rotate(**kwargs)

        elif method == 'strobo':
            self._strobo(**kwargs) 

        else:
            raise ValueError(f"Unknown animation method: {method}")

    def _rotate(self, step=1, cmap='hsv', **kwargs):
        logger.info(f"Rotate animation with step: {step}, cmap: {cmap}")
        length = self.pixels.length
        cmap = get_cmap(cmap)
        norm = Normalize(vmin=0, vmax=length)
        scalarMap = cm.ScalarMappable(norm=norm, cmap=cmap)
        colors = ((scalarMap.to_rgba(np.arange(length))*255)[:,:3]).astype(int)    
        
        frame = np.asarray(colors)
        self.pixels[:] = frame
        self.pixels.show()
        try:
            while not self._stop_event.is_set():
                frame = np.roll(frame, step, axis=0)
                self.pixels[:] = frame
                self.pixels.show()
                if self._stop_event.wait(0.01):
                    break
        finally:
            logger.info('Stop Rotate')
            self.pixels.fill((0,0,0))
            self.pixels.show()

    def _strobo(self, on_time=0.01, off_time=0.1, **kwargs):
        logger.info(f"Strobo animation with on_time: {on_time}, off_time: {off_time}")
        color = [255, 255, 255]
        start = time.time()
        flashes = 0
        try:
            while not self._stop_event.is_set():
                self.pixels.fill(color)
                self.pixels.show()
                if self._stop_event.wait(on_time):
                    break

                self.pixels.fill((0, 0, 0))
                self.pixels.show()
                if self._stop_event.wait(off_time):
                    break

                flashes += 1
        finally:
            self.pixels.fill((0, 0, 0))
            self.pixels.show()
            logger.info("Stop Strobo")
            logger.info("%d flashes in %.2f sec", flashes, time.time() - start)

    def _simulate_fire(self, cooling=120, sparking=120, speed=0.05, **kwargs):
        logger.info(f"Fire animation with cooling: {cooling}, sparking: {sparking}, speed: {speed}")
        import random
        # Array, um die Temperatur jeder einzelnen LED zu speichern (0 = aus, 255 = maximale Hitze)
        heat_raw = [0] * (self.pixels.length // 2)

        try:
            while not self._stop_event.is_set():

                # Step 1: Alle LEDs ein Stück abkühlen
                for i in range(len(heat_raw)):
                    cooldown = random.randint(0, int(((cooling * 10) / len(heat_raw)) + 2))
                    if cooldown > heat_raw[i]:
                        heat_raw[i] = 0
                    else:
                        heat_raw[i] = heat_raw[i] - cooldown

                # Step 2: Hitze steigt nach oben und driftet weg
                for k in range(len(heat_raw) - 1, 1, -1):
                    heat_raw[k] = (heat_raw[k - 1] + heat_raw[k - 2] + heat_raw[k - 2]) // 3

                # Step 3: Zufällig neue Funken an der Basis zünden
                if random.randint(0, 255) < sparking:
                    y = random.randint(0, 3)  # Funke entsteht in den ersten paar LEDs
                    heat_raw[y] = heat_raw[y] + random.randint(160, 255)
                    # Begrenzen auf Maximum
                    if heat_raw[y] > 255:
                        heat_raw[y] = 255

                heat = heat_raw[::-1] + heat_raw  # Spiegeln, um die volle Länge zu erhalten
                # Step 4: Hitze-Werte in RGB-Feuerfarben umrechnen
                for j in range(len(heat)):
                    # Farbskala: Hitze (0-255) -> Schwarz -> Rot -> Orange -> Gelb -> Weiß
                    t150 = int((heat[j] / 255.0) * 150)
                    heat_ramp = heat[j] & 0x3F  # 0 bis 63
                    heat_ramp <<= 2             # 0 bis 252

                    if t150 > 100:
                        # Sehr heiß: Gelb/Weiß
                        self.pixels[j] = (255, 255, heat_ramp)
                    elif t150 > 50:
                        # Mittlere Hitze: Orange
                        self.pixels[j] = (255, heat_ramp, 0)
                    else:
                        # Kühlere Hitze: Rot/Dunkelrot
                        self.pixels[j] = (heat_ramp, 0, 0)

                self.pixels.show()
                if self._stop_event.wait(speed):
                    break

        finally:
            logger.info('Stop Fire Simulation')
            self.pixels.fill((0,0,0))
            self.pixels.show()


def animation():
    """ move leds in rythm of music"""
   
    length = 219
  
    brightness = 1
    pixels = LedStrip(count=length, brightness=brightness)
    
    animation = Animation(pixels) 
    animation.start("rotate")
    input('enter to stop')
    animation.stop()

        
def animate_strobo():
    """ move leds in rythm of music"""
    length = 219
    brightness = 1
    pixels = LedStrip(count=length, brightness=brightness, hardware="arduino")
    animation = Animation(pixels) 
    animation.start("strobo")

    input('enter to stop')
    animation.stop()

def animate_fire():
    """ move leds in rythm of music"""
    length = 219
    brightness = 1
    pixels = LedStrip(count=length, brightness=brightness, hardware="arduino")
    animation = Animation(pixels) 
    animation.start("fire")

    input('enter to stop')
    animation.stop()


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
        
        
        
