from settings import *
from controller_mappings import *

class Controls:

    def __init__(self, keyboard_active_flag):
        pygame.joystick.init()
        self.joystick = None
        self.keyboard_active = keyboard_active_flag
    
        
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
            # print(event.button)
            return ConEventMessage(button=True, scancode=event.button)
        if event.type == pygame.JOYBUTTONUP:
            return ConEventMessage(button=True, scancode=event.button, release=True)

        if self.keyboard_active:
            if event.type == pygame.KEYDOWN:
                # print(event.scancode)
                return ConEventMessage(key=True, scancode=event.scancode)
            if event.type == pygame.KEYUP:
                return ConEventMessage(key=True, scancode=event.scancode, release=True)
        
        return None

        
    def get_event_details(self, con_event_msg: ConEventMessage):
        active = []
        if con_event_msg.has_button:
            type = ConType.CONT_SWITCH
            btn_mapping = CONT_SWITCH_BTN
            if btn_mapping.get(con_event_msg.scancode):
                active.append(btn_mapping.get(con_event_msg.scancode))
        if con_event_msg.has_keypress:
            type = ConType.KEYBOARD
            btn_mapping = CONT_KEYBOARD
            if btn_mapping.get(con_event_msg.scancode):
                active.append(btn_mapping.get(con_event_msg.scancode))
        return ConSignalMessage(type, active, con_event_msg.release) if len(active) > 0 else None

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



