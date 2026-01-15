import spidev as SPI
from lib import LCD_1inch28
from PIL import Image
import numpy as np
from settings import *

RST = 27
DC = 25
BL = 13
bus = 0 
device = 0 

class Display(LCD_1inch28.LCD_1inch28):
    def __init__(self):
        super().__init__()
        self.Init()
        self.clear()
        self.bl_DutyCycle(25)

    def on(self):
        print("Display ON")

    def off(self):
        print("Display OFF")
        self.clear()

    def render2(self, screen):
        data = pygame.image.tostring(screen, "RGB")
        data_pil = Image.frombytes("RGB", screen.get_size(), data)
        self.ShowImage(data_pil)

    def render(self, screen):
        # 1. Get raw RGB data from Pygame (24-bit)
        # We use surfarray because it's a zero-copy view of the pixels
        img = pygame.surfarray.array3d(screen)
        
        # 2. Pygame is [width, height], LCD is [height, width]
        img = img.transpose([1, 0, 2])

        # 3. Fast NumPy conversion to RGB565 (16-bit)
        # Red: 5 bits, Green: 6 bits, Blue: 5 bits
        r = (img[:,:,0] >> 3).astype(np.uint16) << 11
        g = (img[:,:,1] >> 2).astype(np.uint16) << 5
        b = (img[:,:,2] >> 3).astype(np.uint16)
        
        rgb565 = r | g | b
        
        # 4. Convert to Big-Endian bytes (standard for these LCDs)
        # .byteswap() ensures the high/low bytes are in the right order for SPI
        raw_buffer = rgb565.byteswap().tobytes()

        # 5. Push directly to hardware, bypassing ShowImage
        self.SetWindows(0, 0, self.width, self.height)
        self.digital_write(self.DC_PIN, True) # Set DC to Data mode
        
        # Write the whole buffer at once. spidev handles the slicing internally.
        self.SPI.writebytes2(raw_buffer)

    def show_message(self, msg):
        print(f"Display message: {msg}")
