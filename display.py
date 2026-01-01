import spidev as SPI
from lib import LCD_1inch28
from PIL import Image
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
        self.bl_DutyCycle(50)

    def on(self):
        print("Display ON")

    def off(self):
        print("Display OFF")
        self.clear()

    def render(self, screen):
        data = pygame.image.tostring(screen, "RGB")
        data_pil = Image.frombytes("RGB", screen.get_size(), data)
        self.ShowImage(data_pil)

    def show_message(self, msg):
        print(f"Display message: {msg}")
