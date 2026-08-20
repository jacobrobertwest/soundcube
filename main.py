from settings import *
from controls import *
from controller_mappings import *
from repeater import *
from state import *
from synth import *
import midi_devices

if SOUNDCUBE_MODE == "dev":
    from dummy import *
elif SOUNDCUBE_MODE == "prod":
    from display import *
    os.environ["SDL_VIDEODRIVER"] = "dummy"

def main(soundcube_mode):
    screen = pygame.display.set_mode((WIDTH, HEIGHT))
    pygame.display.set_caption("SoundCube")

    if soundcube_mode == "dev":
        KEYBOARD_ACTIVE = True
    else:
        KEYBOARD_ACTIVE = False

    # initialize primary companents
    clock = pygame.time.Clock()
    controls = Controls(KEYBOARD_ACTIVE)
    repeater = UIRepeater(200)
    synth = Synth(soundcube_mode)
    display = Display()

    print(f"[MIDI] {midi_devices.describe()}")

    # initialize state machine
    boot_state = BootState(None, synth, display, soundcube_mode)
    machine = StateMachine(boot_state)
    boot_state.machine = machine
    machine.start()

    # main game loop
    done = False
    midi_device_count = -1        # forces a poll on the first iteration
    last_midi_poll = -MIDI_POLL_MS
    while not done:
        messages = []

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                machine.change(ShutdownState(machine, synth, display))
                done = True
            msg = controls.handle_event(event)
            if msg:
                messages.append(msg)

        # Dispatch button events before anything renders, so a drum pad's noteon is
        # never sitting behind a screen redraw.
        actions_fired = 0
        for c_ed in controls.get_event_details(messages):
            # c_ed.to_string()
            machine.handle_input(c_ed)
            actions_fired += 1

        # Triggers that report as axes rather than buttons are polled, and dispatched
        # here so a drum pad bound to one still fires before anything renders.
        for c_te in controls.get_trigger_events(CONT_SWITCH_TRIGGER_ACTIVE):
            machine.handle_input(c_te)
            actions_fired += 1

        # axis navigation (polled)
        if machine.state.uses_axis_edges:
            # One step per flick: used where a direction means "advance", not "hold
            # to repeat", so it bypasses the repeater entirely.
            for action in controls.get_axis_edges(CONT_SWITCH_AXIS):
                machine.handle_input(ConSignalMessage(ConType.CONT_SWITCH, [action]))
                actions_fired += 1
        else:
            for action in controls.get_axis_state(CONT_SWITCH_AXIS):
                if repeater.allow(action):
                    c_aa = ConSignalMessage(ConType.CONT_SWITCH, [action])
                    machine.handle_input(c_aa)
                    actions_fired += 1

        # Watch for controllers appearing or disappearing. Polled about once a
        # second rather than per frame: a /proc read is cheap but at 120Hz it would
        # be pure waste, and it must never sit in the drum-pad path.
        now = pygame.time.get_ticks()
        if now - last_midi_poll >= MIDI_POLL_MS:
            last_midi_poll = now
            connected = midi_devices.device_count()
            # Re-asserted every poll, not just on a change: fluidsynth's ALSA ports
            # appear a moment after launch, so a single attempt at boot can run
            # before there is anywhere to route the second controller to.
            if connected >= 2:
                midi_devices.ensure_second_device_routed()
            if connected != midi_device_count:
                midi_device_count = connected
                print(f"[MIDI] {connected} controller(s) connected")
                if synth.set_dual_mode(connected >= 2):
                    # The voice readout appears or disappears, so force a repaint.
                    if hasattr(machine.state, 'needs_initial_display'):
                        machine.state.needs_initial_display = True

        # States choose their own loop rate; drum mode needs a far finer poll than
        # the 33ms the UI is happy with.
        dt = clock.tick(machine.state.tick_hz)
        machine.update(dt)

        # Counting dispatched actions rather than raw deflection means a held stick
        # that the repeater is throttling doesn't force a redraw every frame.
        needs_display_render = machine.render(screen, actions_fired > 0)

        # render to the connected LCD display. Pushing a frame is ~115KB over SPI
        # (~38ms at 24MHz), so it only happens when something actually changed.
        if needs_display_render:
            display.render(screen)
            pygame.display.flip()

        # pygame.display.set_caption(f"SoundCube {pygame.mouse.get_pos()}")
if __name__ == '__main__':
    try:
        main(SOUNDCUBE_MODE)
    except:
        os.system("killall fluidsynth")
        raise
