# -------------------------
# Controller button mapper
# -------------------------
# Walks you through pressing each control and prints a paste-ready
# CONT_SWITCH_BTN_MAC table for controller_mappings.py.
#
# The same physical pad enumerates its buttons differently on macOS and Linux,
# which is why two tables exist. Run this on the machine you need a table for:
#
#   python3 scripts/pad_mapper.py
#
# A small window opens - keep it focused. SPACE skips a control the pad lacks,
# ESC quits early and still prints whatever was captured.
#
#   python3 scripts/pad_mapper.py --watch
#
# Watch mode instead dumps every button, axis and hat change live. Use it when a
# control cannot be captured: analog triggers often report as an axis rather than a
# button, so pressing them produces no JOYBUTTONDOWN for the prompts to catch.
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
os.environ.setdefault("SOUNDCUBE_MODE", "dev")

import pygame
from settings import ConButton

# Order matters only for how you are prompted. Directions are handled separately
# because they usually come from an axis or a hat rather than a button.
PROMPTS = [
    (ConButton.A,     "A"),
    (ConButton.B,     "B"),
    (ConButton.X,     "X"),
    (ConButton.Y,     "Y"),
    (ConButton.L,     "L  (left shoulder)"),
    (ConButton.Z,     "Z  (right shoulder / R)"),
    (ConButton.ZL,    "ZL (left trigger)"),
    (ConButton.ZR,    "ZR (right trigger)"),
    (ConButton.MINUS, "MINUS  (-)"),
    (ConButton.PLUS,  "PLUS   (+)"),
    (ConButton.L3,    "L3 (click the LEFT stick)"),
    (ConButton.R3,    "R3 (click the RIGHT stick)"),
    (ConButton.HOME,  "HOME"),
    (ConButton.SCRSH, "SCREENSHOT / capture"),
]

DIRECTIONS = [
    (ConButton.UP,    "D-pad UP"),
    (ConButton.DOWN,  "D-pad DOWN"),
    (ConButton.LEFT,  "D-pad LEFT"),
    (ConButton.RIGHT, "D-pad RIGHT"),
]


def watch(joystick, n_axis, n_hat, show, font, small):
    """Dump every input change live, so a control that the prompts cannot capture
    can be identified. An analog trigger shows up here as an axis, not a button."""
    print("WATCH MODE - press anything. ESC or close the window to stop.\n")
    baseline = [joystick.get_axis(a) for a in range(n_axis)]
    reported = {}
    seen_axes, seen_buttons, seen_hats = set(), set(), set()
    show(("Watch mode: press anything", font), ("ESC to stop", small))
    while True:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                return seen_buttons, seen_axes, seen_hats
            if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                return seen_buttons, seen_axes, seen_hats
            if event.type == pygame.JOYBUTTONDOWN:
                seen_buttons.add(event.button)
                print(f"  BUTTON {event.button:2d} down")
            elif event.type == pygame.JOYBUTTONUP:
                print(f"  BUTTON {event.button:2d} up")
            elif event.type == pygame.JOYHATMOTION:
                seen_hats.add(event.value)
                print(f"  HAT    {event.hat} -> {event.value}")
            elif event.type == pygame.JOYAXISMOTION:
                moved = event.value - baseline[event.axis]
                if abs(moved) < 0.25:
                    continue
                # Only reprint when it changes meaningfully, or the log floods.
                last = reported.get(event.axis)
                if last is not None and abs(event.value - last) < 0.20:
                    continue
                reported[event.axis] = event.value
                seen_axes.add(event.axis)
                print(f"  AXIS   {event.axis:2d} = {event.value:+.2f} "
                      f"(rest {baseline[event.axis]:+.2f}, moved {moved:+.2f})")
        pygame.time.wait(10)


def sample_triggers(joystick, n_axis, show, font, small):
    """Read the axes while a control is physically held.

    Watch mode cannot tell which press produced which value, and a trigger that
    reports both +1 and -1 is ambiguous. Holding it and sampling is unambiguous.
    """
    baseline = [joystick.get_axis(a) for a in range(n_axis)]
    print(f"\nbaseline axes: {' '.join(f'{a}:{v:+.2f}' for a, v in enumerate(baseline))}")
    results = {}
    for label in ("ZL (left trigger)", "ZR (right trigger)",
                  "L (left shoulder)", "R / Z (right shoulder)"):
        show((f"HOLD {label}", font), ("then press SPACE", small),
             ("ESC to skip to the end", small))
        print(f"\nHold {label} down and press SPACE (keep holding)...")
        while True:
            stop = False
            done = False
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    stop = True
                elif event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_SPACE:
                        done = True
                    elif event.key == pygame.K_ESCAPE:
                        stop = True
            if stop:
                return results
            if done:
                break
            pygame.time.wait(10)

        pressed_axes, pressed_buttons = [], []
        for a in range(n_axis):
            value = joystick.get_axis(a)
            if abs(value - baseline[a]) > 0.4:
                pressed_axes.append((a, value))
        for b in range(joystick.get_numbuttons()):
            if joystick.get_button(b):
                pressed_buttons.append(b)
        results[label] = (pressed_axes, pressed_buttons)
        axis_text = ', '.join(f"axis {a} = {v:+.2f}" for a, v in pressed_axes) or 'none'
        btn_text = ', '.join(f"button {b}" for b in pressed_buttons) or 'none'
        print(f"  while held -> {axis_text}   |   {btn_text}")

    print("\n" + "=" * 66)
    print("Summary:")
    for label, (axes_hit, buttons_hit) in results.items():
        print(f"  {label:26s} axes={axes_hit or '-'} buttons={buttons_hit or '-'}")
    print("=" * 66)
    return results


def main():
    pygame.init()
    screen = pygame.display.set_mode((420, 140))
    pygame.display.set_caption("SoundCube pad mapper - keep this window focused")
    font = pygame.font.Font(None, 26)
    small = pygame.font.Font(None, 20)

    def show(*lines):
        screen.fill((24, 24, 28))
        for i, (text, f) in enumerate(lines):
            surf = f.render(text, True, (235, 235, 235))
            screen.blit(surf, (16, 18 + i * 30))
        pygame.display.flip()

    show(("Connect the controller...", font))
    joystick = None
    while joystick is None:
        for event in pygame.event.get():
            if event.type == pygame.JOYDEVICEADDED:
                joystick = pygame.joystick.Joystick(event.device_index)
            elif event.type in (pygame.QUIT, pygame.KEYDOWN):
                if event.type == pygame.QUIT or event.key == pygame.K_ESCAPE:
                    print("No controller connected.")
                    return
        pygame.time.wait(50)

    n_btn, n_axis, n_hat = (joystick.get_numbuttons(), joystick.get_numaxes(),
                            joystick.get_numhats())
    print(f"\nController: {joystick.get_name()!r}")
    print(f"  {n_btn} buttons, {n_axis} axes, {n_hat} hats")
    resting = [f"{a}:{joystick.get_axis(a):+.2f}" for a in range(n_axis)]
    print(f"  resting axes: {' '.join(resting) or '(none)'}")
    offset = [a for a in range(n_axis) if abs(joystick.get_axis(a)) > 0.5]
    if offset:
        print(f"  NOTE axes {offset} rest away from zero (normal for analog triggers)")
    if "--watch" in sys.argv:
        watch(joystick, n_axis, n_hat, show, font, small)
        pygame.quit()
        return

    if "--triggers" in sys.argv:
        sample_triggers(joystick, n_axis, show, font, small)
        pygame.quit()
        return

    print("\nPress each control as prompted. SPACE to skip, ESC to stop early.\n")

    buttons, axes_found, hats_found, aborted = {}, {}, {}, False

    def wait_for(label, kind):
        """Return ('button', idx) / ('axis', idx, sign) / ('hat', value) / None."""
        nonlocal aborted
        show((f"Press: {label}", font),
             ("SPACE = skip    ESC = stop", small),
             (f"captured {len(buttons)} buttons", small))
        # Ignore whatever is already deflected so a resting trigger isn't captured.
        baseline = [joystick.get_axis(a) for a in range(n_axis)]
        pygame.event.clear()
        while True:
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    aborted = True
                    return None
                if event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_ESCAPE:
                        aborted = True
                        return None
                    if event.key == pygame.K_SPACE:
                        return None
                if event.type == pygame.JOYBUTTONDOWN:
                    while any(e.type == pygame.JOYBUTTONUP
                              for e in pygame.event.get(pygame.JOYBUTTONUP)):
                        pass
                    return ('button', event.button)
                if kind == 'direction':
                    if event.type == pygame.JOYHATMOTION and event.value != (0, 0):
                        return ('hat', event.value)
                    if event.type == pygame.JOYAXISMOTION:
                        moved = event.value - baseline[event.axis]
                        if abs(moved) > 1.2:
                            return ('axis', event.axis,
                                    1 if event.value > 0 else -1)
            pygame.time.wait(10)

    for button, label in PROMPTS:
        result = wait_for(label, 'button')
        if aborted:
            break
        if result is None:
            print(f"  {label:34s} skipped")
            continue
        if result[0] == 'button':
            index = result[1]
            clash = buttons.get(index)
            buttons[index] = button
            note = f"  (was {clash.name}, overwritten)" if clash else ""
            print(f"  {label:34s} -> button {index}{note}")

    if not aborted:
        print()
        for button, label in DIRECTIONS:
            result = wait_for(label, 'direction')
            if aborted:
                break
            if result is None:
                print(f"  {label:34s} skipped")
                continue
            if result[0] == 'hat':
                hats_found[result[1]] = button
                print(f"  {label:34s} -> hat value {result[1]}")
            elif result[0] == 'axis':
                axes_found[(result[1], result[2])] = button
                print(f"  {label:34s} -> axis {result[1]} "
                      f"{'positive' if result[2] > 0 else 'negative'}")
            else:
                buttons[result[1]] = button
                print(f"  {label:34s} -> button {result[1]}")

    pygame.quit()

    print("\n" + "=" * 66)
    print("Paste this over CONT_SWITCH_BTN_MAC in controller_mappings.py:\n")
    print("CONT_SWITCH_BTN_MAC = {")
    for index in range(max(n_btn, max(buttons, default=-1) + 1)):
        mapped = buttons.get(index)
        print(f"    {index:2d} : ConButton.{mapped.name},"
              if mapped else f"    {index:2d} : \"\",")
    print("}")

    if hats_found:
        print("\nD-pad reports as a HAT. CONT_SWITCH_HAT already covers the standard")
        print("values; confirm these match what you saw:")
        for value, button in sorted(hats_found.items(), key=lambda kv: str(kv[0])):
            print(f"    {value} -> {button.name}")
    if axes_found:
        print("\nD-pad reports on AXES. Check CONT_SWITCH_AXIS matches:")
        by_axis = {}
        for (axis, sign), button in axes_found.items():
            by_axis.setdefault(axis, {})[sign] = button
        for axis in sorted(by_axis):
            neg = by_axis[axis].get(-1)
            pos = by_axis[axis].get(1)
            neg_text = f"ConButton.{neg.name}" if neg else '""'
            pos_text = f"ConButton.{pos.name}" if pos else '""'
            print(f"    {axis} : [{neg_text}, {pos_text}],")
    if not hats_found and not axes_found:
        print("\nNo directions captured - the D-pad may report as plain buttons,")
        print("in which case they are already in the table above.")
    print("=" * 66)


if __name__ == "__main__":
    main()
