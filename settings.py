import pygame
from enum import Enum
import json

pygame.display.init()
pygame.joystick.init()
pygame.font.init()

PRIMARY_FONT_FP = 'files/font/Futura.otf'
PRIMARY_FONT = pygame.font.Font(PRIMARY_FONT_FP, 18)
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
    def __init__(self, button: bool, axis: bool):
        self.has_button = button
        self.has_axis = axis

class ConSignalMessage:
    def __init__(self, c_type: ConType, c_buttons):
        self.c_type = c_type
        self.c_button = c_buttons

    def to_string(self):
        print(f"[CONT MSG: {self.c_type}, {self.c_button}]")
