from settings import *
from controller_mappings import *

class Controls:

    def __init__(self, keyboard_active_flag):
        pygame.joystick.init()
        self.joystick = None
        self.num_buttons = 0
        self.num_axes = 0
        self.keyboard_active = keyboard_active_flag
        # Platform-selected: the Pi and a mac dev machine enumerate the same pad's
        # buttons differently. See CONT_SWITCH_BTN_ACTIVE.
        self.switch_button_mapping = CONT_SWITCH_BTN_ACTIVE
        self.keyboard_button_mapping = CONT_KEYBOARD
        self.num_hats = 0
        self.hat_state = {}
        # Analog triggers reported as axes: latched pressed/released per axis.
        self.trigger_state = {}
        # Buttons physically down right now. Chords are checked against this rather
        # than against whatever happened to arrive in one event batch, so
        # hold-one-press-the-other works and a mixed press/release batch cannot be
        # misread as a chord.
        self.held = set()
        # Per-axis latched direction (-1 / 0 / +1) for edge detection.
        self.axis_dir = {}
        # Axes confirmed to have rested near centre at least once. Analog triggers
        # commonly rest at -1.0, which otherwise reads as a permanent full
        # deflection and fires a spurious direction the moment we start polling.
        self.axis_centred = set()

    def handle_event(self, event: pygame.event):
        if event.type == pygame.JOYDEVICEADDED:
            joy = pygame.joystick.Joystick(event.device_index)
            self.joystick = joy
            self.joystick_id = joy.get_instance_id()
            self.num_buttons = joy.get_numbuttons()
            self.num_axes = joy.get_numaxes()
            self.num_hats = joy.get_numhats()
            self.axis_dir.clear()
            self.axis_centred.clear()
            self.hat_state.clear()
            print(f"Joystick {self.joystick_id} connected: {joy.get_name()!r} "
                  f"({self.num_buttons} buttons, {self.num_axes} axes, "
                  f"{self.num_hats} hats)")
            # Resting axis values matter: any mapped axis that rests away from 0
            # (analog triggers usually rest at -1.0) would read as a held
            # direction. Printed once so a misbehaving pad is diagnosable.
            resting = [f"{a}:{joy.get_axis(a):+.2f}" for a in range(self.num_axes)]
            print(f"  resting axes {' '.join(resting)}")
            offset = [a for a in range(self.num_axes)
                      if abs(joy.get_axis(a)) > 0.5 and CONT_SWITCH_AXIS.get(a)]
            if offset:
                print(f"  NOTE axes {offset} rest deflected and are mapped to "
                      f"directions; ignoring them until they centre")

        if event.type == pygame.JOYDEVICEREMOVED:
            self.joystick = None
            self.num_axes = 0
            self.num_hats = 0
            # Anything still down is unknowable now; drop it so nothing sticks.
            self.held.clear()
            self.axis_dir.clear()
            self.axis_centred.clear()
            self.hat_state.clear()
            self.trigger_state.clear()
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


    def get_event_details(self, con_event_msg: list[ConEventMessage]):
        """One ConSignalMessage per physical event, in arrival order.

        Collapsing a whole batch into a single message meant the last event's
        release flag was applied to every button in it, which both dropped presses
        and invented chords that were never pressed.
        """
        signals = []
        for msg in con_event_msg:
            if msg.has_button:
                c_type = ConType.CONT_SWITCH
                button = self.switch_button_mapping.get(msg.scancode)
            elif msg.has_keypress:
                c_type = ConType.KEYBOARD
                button = self.keyboard_button_mapping.get(msg.scancode)
            else:
                continue
            if not button:
                continue
            if msg.release:
                self.held.discard(button)
            else:
                self.held.add(button)
            signals.append(
                ConSignalMessage(c_type, [button], msg.release, held=self.held))
        return signals

    def _axis_mappings(self, axis_mapping):
        """Axes the pad reports that we also have a mapping for.

        CONT_SWITCH_AXIS only covers axes 0-5; a pad reporting more (triggers and
        hats often show up as extra axes) used to raise KeyError on the first poll.
        """
        for axis in range(self.num_axes):
            mapping = axis_mapping.get(axis)
            if mapping:
                yield axis, mapping

    def get_trigger_events(self, trigger_mapping, on_threshold=0.2,
                           off_threshold=-0.2):
        """Analog triggers reported as axes, surfaced as ordinary button events.

        On this pad's macOS driver ZL/ZR are axes 4/5 rather than buttons, so
        without this they cannot be used at all - which left two drum pads dead.

        SDL reports such an axis as 0.00 until its first report, then -1.00 at rest
        and +1.00 fully pressed. Both 0.00 and -1.00 sit below on_threshold, so an
        untouched trigger never registers a phantom press, and the gap between the
        thresholds gives hysteresis.

        Returns ConSignalMessages identical in shape to real button events, and
        keeps self.held in step so chords behave the same way.
        """
        if not self.joystick:
            return []

        events = []
        for axis, button in trigger_mapping.items():
            if not button or axis >= self.num_axes:
                continue
            value = self.joystick.get_axis(axis)
            was_pressed = self.trigger_state.get(axis, False)
            if not was_pressed and value >= on_threshold:
                pressed = True
            elif was_pressed and value <= off_threshold:
                pressed = False
            else:
                pressed = was_pressed
            if pressed == was_pressed:
                continue
            self.trigger_state[axis] = pressed
            if pressed:
                self.held.add(button)
            else:
                self.held.discard(button)
            events.append(ConSignalMessage(ConType.CONT_SWITCH, [button],
                                          release=not pressed, held=self.held))
        return events

    def _hat_directions(self):
        """Current hat directions. Many pads expose the D-pad as a hat, which the
        axis tables never see, so directions would otherwise be dead."""
        directions = []
        for hat in range(self.num_hats):
            btn = CONT_SWITCH_HAT.get(self.joystick.get_hat(hat))
            if btn:
                directions.append(btn)
        return directions

    def get_axis_state(self, axis_mapping, threshold=0.95):
        """Currently deflected directions, repeated every call while held."""
        if not self.joystick:
            return []

        active = []
        for axis, mapping in self._axis_mappings(axis_mapping):
            axpos = self.joystick.get_axis(axis)
            if abs(axpos) > threshold:
                z = 0 if axpos < 0 else 1
                # print(f'{axis}: {z}')
                btn = mapping[z]
                if btn != "":
                    active.append(btn)
        active.extend(self._hat_directions())
        return active

    def get_axis_edges(self, axis_mapping, on_threshold=0.95, off_threshold=0.80):
        """Only fresh deflections, one per flick.

        Hysteresis (latch at 0.95, release below 0.80) keeps a stick resting near
        the threshold from chattering. Used where a direction means "advance one
        step" rather than "hold to repeat".
        """
        if not self.joystick:
            return []

        edges = []
        for axis, mapping in self._axis_mappings(axis_mapping):
            axpos = self.joystick.get_axis(axis)

            # Until an axis has been seen near centre, treat whatever it reports as
            # its resting position. Without this, a trigger resting at -1.0 fires a
            # direction on the very first poll - which in drum mode meant an
            # unrequested kit change.
            if axis not in self.axis_centred:
                if abs(axpos) < off_threshold:
                    self.axis_centred.add(axis)
                continue

            previous = self.axis_dir.get(axis, 0)

            if axpos <= -on_threshold:
                current = -1
            elif axpos >= on_threshold:
                current = 1
            elif abs(axpos) < off_threshold:
                current = 0
            else:
                current = previous  # in the hysteresis band, hold the latch

            if current != previous:
                self.axis_dir[axis] = current
                if current != 0:
                    btn = mapping[0 if current < 0 else 1]
                    if btn != "":
                        edges.append(btn)

        # Hats are already discrete, so an edge is simply a change of value.
        for hat in range(self.num_hats):
            value = self.joystick.get_hat(hat)
            if value != self.hat_state.get(hat, (0, 0)):
                self.hat_state[hat] = value
                btn = CONT_SWITCH_HAT.get(value)
                if btn:
                    edges.append(btn)
        return edges
