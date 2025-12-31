import pygame
from enum import Enum
import glob
import os
import json

pygame.display.init()
pygame.joystick.init()
pygame.font.init()

PRIMARY_FONT_FP = 'files/font/Futura.otf'
GAMECUBE_FONT_FP = 'files/font/GameCube.ttf'
MARIO_FONT_FP = 'files/font/Mario.ttf'
EARTHBOUND_FONT_FP = 'files/font/Earthbound.otf'

PRIMARY_FONT = pygame.font.Font(PRIMARY_FONT_FP, 18)
SECONDARY_FONT = pygame.font.Font(PRIMARY_FONT_FP, 14)
GCN_FONT = pygame.font.Font(GAMECUBE_FONT_FP, 12)
PRESET_FONT = pygame.font.Font(MARIO_FONT_FP, 90)

PRESET_COLORS = [
    (0, 156, 218),
    (252, 208, 0),
    (231, 31, 5),
    (66, 176, 50),
]

# screen width and height (pixels)
WIDTH = 240
HEIGHT = 240

class ConType(Enum):
    KEYBOARD = 0
    CONT_SWITCH = 1

class ConButton(Enum):
    LEFT = 0
    RIGHT = 1
    UP = 2
    DOWN = 3
    A = 4
    B = 5
    X = 6
    Y = 7
    PLUS = 8

class ConEventMessage:
    def __init__(self, button: bool = False, key: bool = False, scancode: int = None):
        self.has_button = button
        self.has_keypress = key
        self.scancode = scancode

class ConSignalMessage:
    def __init__(self, c_type: ConType, c_buttons):
        self.c_type = c_type
        self.c_button = c_buttons

    def to_string(self):
        print(f"[CONT MSG: {self.c_type}, {self.c_button}]")
