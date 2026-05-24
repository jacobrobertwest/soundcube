from settings import *
from controls import *
from controller_mappings import *
from repeater import *
from state import *
from synth import *

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

    # initialize state machine
    boot_state = BootState(None, synth, display, soundcube_mode)
    machine = StateMachine(boot_state)
    boot_state.machine = machine
    machine.start()

    # main game loop
    done = False
    while not done:
        messages = []

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                machine.change(ShutdownState(machine, synth, display))
                done = True
            msg = controls.handle_event(event)
            if msg:
                messages.append(msg)

        if messages:
            c_ed = controls.get_event_details(messages)
            if c_ed:
                # c_ed.to_string()
                machine.handle_input(c_ed)

        # axis navigation (polled)
        axis_actions = controls.get_axis_state(CONT_SWITCH_AXIS)
        for action in axis_actions:
            if repeater.allow(action):
                c_aa = ConSignalMessage(ConType.CONT_SWITCH, [action])
                machine.handle_input(c_aa)

        dt = clock.tick(30)
        machine.update(dt)
        has_event = True if len(messages) > 0 or len(axis_actions) > 0 else False
        needs_display_render = machine.render(screen, has_event)
        
        # render to the connected LCD display
        # if needs_display_render:
        #     display.render(screen)
        #     pygame.display.flip()
    
        display.render(screen)
        pygame.display.flip()
        
        # pygame.display.set_caption(f"SoundCube {pygame.mouse.get_pos()}")
if __name__ == '__main__':
    try:
        main(SOUNDCUBE_MODE)
    except:
        os.system("killall fluidsynth")
        raise
