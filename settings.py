import pygame
from enum import Enum
import glob
import os
import json
from copy import deepcopy

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

FX_LIBRARY = {
    "gain": { 
        "def": 2.0,                     # default value
        "rng": (0.0,5.0),                   # min max value range (if tuple, stop at top/bottom, if list, flip between values)
        "incr": 0.1,                    # increment value by
        "cmd": "gain {val}",      # terminal command
        "params": None,                 # list of fx params
    },
    "reverb": {
        "def": 0,
        "rng": (0,1),
        "incr": 1,
        "cmd": "set synth.reverb.active {val}",
        "params": {
                    "room-size": {
                        "def": 0.5,
                        "rng": (0.0,1.0),
                        "incr": 0.05,
                        "cmd": "set synth.reverb.room-size {val}"
                    },
                    "damp": {
                        "def": 0.5,
                        "rng": (0.0,1.0),
                        "incr": 0.05,
                        "cmd": "set synth.reverb.damp {val}"
                    },
                    "width": {
                        "def": 0.5,
                        "rng": (0.0,1.0),
                        "incr": 0.05,
                        "cmd": "set synth.reverb.width {val}"
                    },
                    "level": {
                        "def": 0.5,
                        "rng": (0.0,1.0),
                        "incr": 0.05,
                        "cmd": "set synth.reverb.level {val}"
                    }
                }
    },
    "chorus": {
        "def": 0,
        "rng": (0,1),
        "incr": 1,
        "cmd": "set synth.chorus.active {val}",
        "params": {
                    "nr": {
                        "def": 2,
                        "rng": (0,20),
                        "incr": 1,
                        "cmd": "set synth.chorus.nr {val}"
                    },
                    "level": {
                        "def": 1.5,
                        "rng": (0.0,10.0),
                        "incr": 0.5,
                        "cmd": "set synth.chorus.level {val}"
                    },
                    "speed": {
                        "def": 1.5,
                        "rng": (0.1,5.0),
                        "incr": 0.035,
                        "cmd": "set synth.chorus.speed {val}"
                    },
                    "depth": {
                        "def": 3,
                        "rng": (0,256),
                        "incr": 0.05,
                        "cmd": "set synth.chorus.depth {val}"
                    }
                }
    }
}

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
    MINUS = 9
    Z = 10
    L = 11
    SCRSH = 12
    

class ConEventMessage:
    def __init__(self, button: bool = False, key: bool = False, scancode: int = None, release=False):
        self.has_button = button
        self.has_keypress = key
        self.scancode = scancode
        self.release = release
        self.pressed = not release

class ConSignalMessage:
    def __init__(self, c_type: ConType, c_buttons, release: bool = False):
        self.c_type = c_type
        self.c_button = c_buttons
        self.release = release
        self.pressed = not release

    def to_string(self):
        print(f"[CONT MSG: ({"PRESSED" if not self.release else "RELEASED"}) {self.c_type}, {self.c_button}]")
