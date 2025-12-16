from settings import *
from controls import Controls
from controller_mappings import CONT_SWITCH_BTN, CONT_SWITCH_AXIS
from repeater import UIRepeater
from state import *
from dummy import *

def main():
    pygame.init()
    screen = pygame.display.set_mode((500, 500))
    pygame.display.set_caption("Joystick example")
    clock = pygame.time.Clock()
    controls = Controls()
    synth = DummySynth()
    display = DummyDisplay()
    boot_state = BootState(None, synth, display)
    machine = StateMachine(boot_state)
    boot_state.machine = machine
    machine.start()

    font = pygame.font.Font(None, 36)
    repeater = UIRepeater(200)

    done = False
    while not done:
        messages = []

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                done = True
            msg = controls.handle_event(event)
            if msg:
                messages.append(msg)

        # button presses
        for msg in messages:
            c_ed = controls.get_event_details(msg, CONT_SWITCH_BTN)
            if c_ed:
                machine.handle_input(c_ed)

        # axis navigation (polled)
        axis_actions = controls.get_axis_state(CONT_SWITCH_AXIS)
        for action in axis_actions:
            if repeater.allow(action):
                c_aa = ConSignalMessage(ConType.CONT_SWITCH, [action])
                machine.handle_input(c_aa)

        screen.fill((0, 0, 0))
        dt = clock.tick(30)
        machine.update(dt)
        machine.render(screen)
        pygame.display.flip()

if __name__ == '__main__':
    main()
