import pygame
from enum import Enum
import glob
import os
import sys
import json
import shutil
from copy import deepcopy
import subprocess
import threading
import socket

pygame.display.init()
pygame.joystick.init()
pygame.font.init()

SOUNDCUBE_MODE = os.getenv("SOUNDCUBE_MODE", "prod")

# SOUNDCUBE_DEBUG=1 echoes every command sent to fluidsynth and every drum pad
# action, so an unexpected patch change can be traced to what caused it.
SOUNDCUBE_DEBUG = os.getenv("SOUNDCUBE_DEBUG", "0") != "0"

SOUNDCUBE_VERSION = '1.1.5'

PRIMARY_FONT_FP = 'files/font/Futura.otf'
GAMECUBE_FONT_FP = 'files/font/GameCube.ttf'
MARIO_FONT_FP = 'files/font/Mario.ttf'
EARTHBOUND_FONT_FP = 'files/font/Earthbound.otf'
UNICODE_FONT_FP = 'files/font/unifont.otf'

PRIMARY_FONT = pygame.font.Font(PRIMARY_FONT_FP, 18)
SECONDARY_FONT = pygame.font.Font(PRIMARY_FONT_FP, 14)
UNICODE_FONT = pygame.font.Font(UNICODE_FONT_FP, 15)
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
        "def": 1.0,                     # default value
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
    HOME = 13
    L3 = 14
    R3 = 15
    ZL = 16
    ZR = 17
    DUP = 18
    DDOWN = 19
    DLEFT = 20
    DRIGHT = 21
    

class ConEventMessage:
    def __init__(self, button: bool = False, key: bool = False, scancode: int = None, release=False):
        self.has_button = button
        self.has_keypress = key
        self.scancode = scancode
        self.release = release
        self.pressed = not release

class ConSignalMessage:
    def __init__(self, c_type: ConType, c_buttons, release: bool = False, held=None):
        self.c_type = c_type
        self.c_button = c_buttons
        self.release = release
        self.pressed = not release
        # buttons physically held down at the moment this message was produced.
        # chord checks read this; single-button checks read c_button.
        self.held = frozenset(held) if held is not None else frozenset(c_buttons)

    def to_string(self):
        print(f"[CONT MSG: ({"PRESSED" if not self.release else "RELEASED"}) {self.c_type}, {self.c_button}]")

# -------------------------
# Dual MIDI controller support
# -------------------------
# fluidsynth's ALSA sequencer driver creates one input port per 16 channels, and
# port N maps onto synth channels N*16..N*16+15. Asking for 32 channels therefore
# gives a second port whose channel block is 16-31, which is how a second
# controller gets its own voice regardless of what MIDI channel it transmits on.
#
# This is a startup-only setting, so it is always requested - a controller plugged
# in later has to find the port already there.
MIDI_CHANNELS = 32
VOICE1_CHANNEL = 0
VOICE2_CHANNEL = 16

# How often to look for controllers appearing or disappearing. A /proc read is
# cheap but there is no reason to do it per frame.
MIDI_POLL_MS = 1000

# -------------------------
# Drum performance mode
# -------------------------
# Drum kits live in bank 128 by GM convention.
#
# Channel 9 (MIDI channel 10) is the GM drum channel, and using it keeps drums off
# channel 0, which is shared by the melodic patch, the USB MIDI controller, and
# bootup.mid. A program change on channel 0 - bootup.mid sends one, to program 13 -
# would otherwise replace the drum kit mid-performance, because the router passes
# program changes straight through.
DRUM_BANK = 128
DRUM_CHANNEL = 9

BASE_POLYPHONY = 16     # what post_boot_init sets for melodic play
DRUM_POLYPHONY = 32     # ten pads with cymbal tails will exceed 16 and steal voices

DRUM_VELOCITY_DEFAULT = 110
DRUM_VELOCITY_MIN = 20
DRUM_VELOCITY_MAX = 127
DRUM_VELOCITY_STEP = 8

# Never send noteoff sooner than this after noteon, so a fast tap isn't cut off
# mid-transient. Releases inside the window are deferred by PerformState.update().
DRUM_MIN_GATE_MS = 60

# The ten playable pads, in screen layout order (two columns of five).
PAD_BUTTONS = [
    ConButton.A, ConButton.B, ConButton.X, ConButton.Y, ConButton.L,
    ConButton.Z, ConButton.ZL, ConButton.ZR, ConButton.L3, ConButton.R3,
]

DEFAULT_PAD_NOTES = {
    "A": 36,    # Bass Drum 1
    "B": 38,    # Acoustic Snare
    "X": 42,    # Closed Hi-Hat
    "Y": 46,    # Open Hi-Hat
    "L": 49,    # Crash Cymbal 1
    "Z": 51,    # Ride Cymbal 1
    "ZL": 45,   # Low Tom
    "ZR": 48,   # Hi-Mid Tom
    "L3": 39,   # Hand Clap
    "R3": 56,   # Cowbell
}

# General MIDI Level 1 percussion key map. The soundfonts here are GM-style
# bank-128 kits, so these names describe what actually sounds. Sample names inside
# the SF2 files are placeholders ("Sample 17-4") and useless as labels.
GM_PERCUSSION = {
    35: "Acoustic Bass Drum", 36: "Bass Drum 1",     37: "Side Stick",
    38: "Acoustic Snare",     39: "Hand Clap",       40: "Electric Snare",
    41: "Low Floor Tom",      42: "Closed Hi-Hat",   43: "High Floor Tom",
    44: "Pedal Hi-Hat",       45: "Low Tom",         46: "Open Hi-Hat",
    47: "Low-Mid Tom",        48: "Hi-Mid Tom",      49: "Crash Cymbal 1",
    50: "High Tom",           51: "Ride Cymbal 1",   52: "Chinese Cymbal",
    53: "Ride Bell",          54: "Tambourine",      55: "Splash Cymbal",
    56: "Cowbell",            57: "Crash Cymbal 2",  58: "Vibraslap",
    59: "Ride Cymbal 2",      60: "Hi Bongo",        61: "Low Bongo",
    62: "Mute Hi Conga",      63: "Open Hi Conga",   64: "Low Conga",
    65: "High Timbale",       66: "Low Timbale",     67: "High Agogo",
    68: "Low Agogo",          69: "Cabasa",          70: "Maracas",
    71: "Short Whistle",      72: "Long Whistle",    73: "Short Guiro",
    74: "Long Guiro",         75: "Claves",          76: "Hi Wood Block",
    77: "Low Wood Block",     78: "Mute Cuica",      79: "Open Cuica",
    80: "Mute Triangle",      81: "Open Triangle",
}

# Abbreviations for the 240px round display, which cannot fit full names in a
# ten-pad grid. Anything not listed falls back to a truncated GM name.
GM_PERCUSSION_SHORT = {
    35: "KICK2", 36: "KICK",  37: "STICK", 38: "SNARE", 39: "CLAP",
    40: "ESNR",  41: "FTOM",  42: "CHAT",  43: "FTOM2", 44: "PHAT",
    45: "TOM-L", 46: "OHAT",  47: "TOM-M", 48: "TOM-H", 49: "CRASH",
    50: "TOM-X", 51: "RIDE",  52: "CHINA", 53: "BELL",  54: "TAMB",
    55: "SPLSH", 56: "COWBL", 57: "CRSH2", 58: "VSLAP", 59: "RIDE2",
    60: "BNGO-H", 61: "BNGO-L", 62: "CNGA-M", 63: "CNGA-H", 64: "CNGA-L",
    65: "TMBL-H", 66: "TMBL-L", 67: "AGGO-H", 68: "AGGO-L", 69: "CABSA",
    70: "MARAC", 71: "WHIS-S", 72: "WHIS-L", 73: "GURO-S", 74: "GURO-L",
    75: "CLAVE", 76: "WOOD-H", 77: "WOOD-L", 78: "CUCA-M", 79: "CUCA-O",
    80: "TRI-M", 81: "TRI-O",
}

def drum_label(note, short=False):
    """Human-readable name for a percussion note.

    Notes outside the GM range still occur - poke and sm64 kits carry ~41 each -
    so they get a numeric label rather than being hidden from the editor.
    """
    if short:
        if note in GM_PERCUSSION_SHORT:
            return GM_PERCUSSION_SHORT[note]
        if note in GM_PERCUSSION:
            return GM_PERCUSSION[note].upper()[:6]
        return f"#{note}"
    return GM_PERCUSSION.get(note, f"Note {note}")
