import pygame
from settings import ConButton, ConSignalMessage, ConType

# -------------------------
# Base State and StateMachine
# -------------------------
class State:
    def enter(self): pass
    def exit(self): pass
    def handle_input(self, action: ConSignalMessage): pass
    def update(self, dt): pass
    def render(self, screen): pass

class StateMachine:
    def __init__(self, initial_state: State):
        self.state = initial_state
        
    def start(self):
        self.state.enter()

    def change(self, new_state: State):
        self.state.exit()
        self.state = new_state
        self.state.enter()

    def handle_input(self, action: ConSignalMessage):
        self.state.handle_input(action)

    def update(self, dt):
        self.state.update(dt)

    def render(self, screen):
        self.state.render(screen)

# -------------------------
# Boot State
# -------------------------
class BootState(State):
    def __init__(self, machine, synth, display):
        self.machine = machine
        self.synth = synth
        self.display = display
        self.name = 'boot'

    def enter(self):
        self.display.off()
        ok = self.synth.start()
        if ok:
            self.display.on()
            self.machine.change(PerformanceState(self.machine, self.synth, self.display))
        else:
            self.machine.change(ShutdownState(self.machine, self.synth, self.display))

    def handle_input(self, action):
        pass  # ignore input during boot

    def render(self, screen):
        # Optional boot screen
        screen.fill((0, 0, 0))
        font = pygame.font.Font(None, 36)
        text = font.render("Booting...", True, (255, 255, 255))
        screen.blit(text, (20, 20))

# -------------------------
# Patch Mode Base (Performance/Rehearsal)
# -------------------------
class PatchMode(State):
    def __init__(self, machine, synth, display):
        self.machine = machine
        self.synth = synth
        self.display = display
        self.substate = "SELECT"
        self.current_patch = 0
        self.num_patches = 24

    def handle_input(self, action: ConSignalMessage):
        for btn in action.c_button:
            if self.substate == "SELECT":
                self.handle_patch_select(btn)
            elif self.substate == "SETTINGS":
                self.handle_settings(btn)

    def handle_patch_select(self, btn: ConButton):
        if btn == ConButton.LEFT:
            self.current_patch = (self.current_patch - 1) % self.num_patches
            self.synth.load_patch(self.current_patch)
        elif btn == ConButton.RIGHT:
            self.current_patch = (self.current_patch + 1) % self.num_patches
            self.synth.load_patch(self.current_patch)
        elif btn == ConButton.A:
            self.substate = "SETTINGS"
        elif btn == ConButton.Y:
            self.machine.change(ShutdownState(self.machine, self.synth, self.display))
        elif btn == ConButton.PLUS:
            self.toggle_mode()

    def handle_settings(self, btn: ConButton):
        if btn == ConButton.B:
            self.substate = "SELECT"
    
    def toggle_mode(self):
        """Switch between Performance and Rehearsal."""
        if isinstance(self, PerformanceState):
            new_state = RehearsalState(self.machine, self.synth, self.display)
        elif isinstance(self, RehearsalState):
            new_state = PerformanceState(self.machine, self.synth, self.display)
        else:
            return 
        
        new_state.current_patch = self.current_patch
        self.machine.change(new_state)

    def render(self, screen):
        screen.fill((30, 30, 30))
        font = pygame.font.Font(None, 36)
        # Show current patch
        patch_text = font.render(f"Patch: {self.current_patch + 1}", True, (255, 255, 0))
        screen.blit(patch_text, (20, 20))
        # Show substate
        state_text = font.render(f"Mode: {self.substate}", True, (0, 255, 255))
        screen.blit(state_text, (20, 60))
        # show state
        state_name = type(self).__name__
        state_text = font.render(f"State: {state_name}", True, (255, 128, 0))
        screen.blit(state_text, (20, 100))

# -------------------------
# Performance State
# -------------------------
class PerformanceState(PatchMode):

    def handle_settings(self, btn: ConButton):
        if btn == ConButton.UP:
            self.synth.volume_up()
        elif btn == ConButton.DOWN:
            self.synth.volume_down()
        elif btn == ConButton.B:
            self.substate = "SELECT"

# -------------------------
# Rehearsal State
# -------------------------
class RehearsalState(PatchMode):
    def handle_settings(self, btn: ConButton):
        if btn == ConButton.UP:
            self.synth.volume_up()
        elif btn == ConButton.DOWN:
            self.synth.volume_down()
        elif btn == ConButton.X:
            self.synth.save_patch(self.current_patch)
        elif btn == ConButton.B:
            self.substate = "SELECT"

# -------------------------
# Shutdown State
# -------------------------
class ShutdownState(State):
    def __init__(self, machine, synth, display):
        self.machine = machine
        self.synth = synth
        self.display = display
        self.cleaned_up = False

    def enter(self):
        self.display.show_message("Shutting down...")
        self.synth.stop()
        self.display.off()

    def handle_input(self, action):
        pass  # ignore input

    def update(self, dt):
        if not self.cleaned_up:
            pygame.quit()
            self.cleaned_up = True
            raise SystemExit

    def render(self, screen):
        screen.fill((0, 0, 0))
        font = pygame.font.Font(None, 36)
        text = font.render("Shutting down...", True, (255, 0, 0))
        screen.blit(text, (20, 20))
