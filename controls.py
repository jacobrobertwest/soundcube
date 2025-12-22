from settings import *
from controller_mappings import CONT_SWITCH_BTN

class Controls:

    def __init__(self):
        pygame.joystick.init()
        self.joystick = None

    def handle_event(self, event: pygame.event):
        if event.type == pygame.JOYDEVICEADDED:
            joy = pygame.joystick.Joystick(event.device_index)
            self.joystick = joy
            self.joystick_id = joy.get_instance_id()
            self.num_buttons = joy.get_numbuttons()
            self.num_axes = joy.get_numaxes()
            print(f"Joystick {self.joystick_id} connected")

        if event.type == pygame.JOYDEVICEREMOVED:
            self.joystick = None
            print("Joystick disconnected")

        if event.type == pygame.JOYBUTTONDOWN:
            return ConEventMessage(button=True, axis=False)

        return None

        
    def get_event_details(self, con_event_msg: ConEventMessage, btn_mapping):
        active = []
        if con_event_msg.has_button:
            for btn in range(self.num_buttons):
                ## print(f"{btn} : {self.joystick.get_button(btn)}")
                if self.joystick.get_button(btn) == 1:
                    if btn_mapping[btn] != "":
                        active.append(btn_mapping[btn])
        return ConSignalMessage(ConType.CONT_SWITCH, active) if len(active) > 0 else None

    def get_axis_state(self, axis_mapping, threshold=0.95):
        if not self.joystick:
            return []

        active = []
        for axis in range(self.num_axes):
            axpos = self.joystick.get_axis(axis)
            if abs(axpos) > threshold:
                z = 0 if axpos < 0 else 1
                btn = axis_mapping[axis][z]
                if btn != "":
                    active.append(btn)
        return active



