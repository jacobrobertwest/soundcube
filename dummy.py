# -------------------------
# Placeholder Synth
# -------------------------
import os
import json
from settings import *

# -------------------------
# Placeholder Display
# -------------------------
class Display:
    def on(self):
        print("Display ON")

    def off(self):
        print("Display OFF")

    def render(self, screen):
        pass

    def show_message(self, msg):
        print(f"Display message: {msg}")
