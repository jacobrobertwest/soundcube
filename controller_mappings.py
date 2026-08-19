from settings import *

CONT_SWITCH_BTN = {
    0 : ConButton.Y,
    1 : ConButton.B,
    2 : ConButton.A,
    3 : ConButton.X,
    4 : ConButton.L,
    5 : ConButton.Z,
    6 : ConButton.ZL,
    7 : ConButton.ZR,
    8 : ConButton.MINUS,
    9 : ConButton.PLUS, 
    10 : ConButton.L3,
    11 : ConButton.R3,
    12 : ConButton.HOME,
    13 : ConButton.SCRSH,
    14 : "",
    15 : "",
    16 : "",
    17 : "",
    18 : "",
    19 : ""
}

CONT_KEYBOARD = {
    79: ConButton.RIGHT,
    80: ConButton.LEFT,
    81: ConButton.DOWN,
    82: ConButton.UP,
    4: ConButton.A,
    5: ConButton.B,
    27: ConButton.X,
    28: ConButton.Y,
    45: ConButton.MINUS,
    46: ConButton.PLUS,
    15: ConButton.L,
    11: ConButton.HOME,
    29: ConButton.Z,
    30: ConButton.L3,
    39: ConButton.R3,
    # c / v: ZL and ZR had no keyboard equivalent, which left 2 of the 10 drum
    # pads unreachable when testing in dev mode.
    6: ConButton.ZL,
    25: ConButton.ZR,
}

# Mapped from a 'Core (Plus) Wired Controller' on macOS via scripts/pad_mapper.py.
# Note this pad reports its D-pad as plain buttons (11-14), not as a hat or axes,
# so directions arrive as button events here while on the Pi they come from
# CONT_SWITCH_AXIS. Both paths are supported.
CONT_SWITCH_BTN_MAC = {
    0 : ConButton.A,
    1 : ConButton.B,
    2 : ConButton.X,
    3 : ConButton.Y,
    4 : ConButton.MINUS,
    5 : ConButton.HOME,
    6 : ConButton.PLUS,
    7 : ConButton.L3,
    8 : ConButton.R3,
    9 : ConButton.L,
    10 : ConButton.Z,
    11 : ConButton.UP,
    12 : ConButton.DOWN,
    13 : ConButton.LEFT,
    14 : ConButton.RIGHT,
    15 : ConButton.SCRSH,
    16 : "",
    17 : "",
    18 : "",
    19 : ""
}

CONT_SWITCH_AXIS = {
    0 : [ConButton.LEFT, ConButton.RIGHT],
    1 : [ConButton.UP, ConButton.DOWN],
    2 : [ConButton.LEFT, ConButton.RIGHT],
    3 : [ConButton.UP, ConButton.DOWN],
    4 : ["", ""],
    5 : ["", ""],
}

# Many pads report the D-pad as a hat rather than as axes, in which case the axis
# tables above never see it. Hat values are (x, y) with y positive meaning up.
CONT_SWITCH_HAT = {
    (-1,  0): ConButton.LEFT,
    ( 1,  0): ConButton.RIGHT,
    ( 0,  1): ConButton.UP,
    ( 0, -1): ConButton.DOWN,
}

# Analog triggers that report as an axis instead of a button, surfaced as ordinary
# button presses so they can be used as drum pads.
#
# SDL reports such an axis as 0.00 until its first report, then -1.00 at rest and
# +1.00 fully pressed - which is why a release shows up as -1.00 rather than 0.
CONT_SWITCH_TRIGGER_MAC = {
    4 : ConButton.ZL,
    5 : ConButton.ZR,
}

# On the Pi this pad exposes ZL/ZR as plain buttons 6 and 7 (see CONT_SWITCH_BTN),
# so there is nothing to derive from axes there.
CONT_SWITCH_TRIGGER = {}

# The same physical controller enumerates its controls differently depending on the
# host HID driver, so macOS and Linux need separate tables. Selected by platform:
# the Pi gets CONT_SWITCH_BTN, a mac dev machine gets CONT_SWITCH_BTN_MAC.
# Run `python3 scripts/pad_mapper.py` to regenerate the mac table for a new pad.
CONT_SWITCH_BTN_ACTIVE = (
    CONT_SWITCH_BTN_MAC if sys.platform == "darwin" else CONT_SWITCH_BTN
)
CONT_SWITCH_TRIGGER_ACTIVE = (
    CONT_SWITCH_TRIGGER_MAC if sys.platform == "darwin" else CONT_SWITCH_TRIGGER
)
