import pygame
from settings import *
# -------------------------
# Base State and StateMachine
# -------------------------
class State:
    # Loop rate this state wants. The UI is fine at 30, but drum pads need a much
    # finer poll than a 33ms frame allows.
    tick_hz = 30
    # Whether directional axes fire once per flick (edges) or repeat while held.
    uses_axis_edges = False

    def enter(self): pass
    def exit(self): pass
    def handle_input(self, action: ConSignalMessage): pass
    def update(self, dt): pass
    # Returning False means "nothing changed, don't push a frame to the LCD".
    def render(self, screen, event_happened): return False

def perform_system_shutdown(machine, synth, display):
    """Power the device off.

    In dev this must never power off the developer's own machine - SCRSH is mapped
    on the dev controller too, and a 3-second hold would otherwise run
    `sudo shutdown -h now` on a laptop. Mirrors UpdateState.reboot's behaviour.
    """
    display.off()
    if SOUNDCUBE_MODE == "dev":
        print("[DEV] suppressed: sudo shutdown -h now")
        machine.change(ShutdownState(machine, synth, display))
    else:
        os.system("sudo shutdown -h now")


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

    def render(self, screen, event_happened):
        rtn = self.state.render(screen, event_happened)
        return rtn

# -------------------------
# Boot State
# -------------------------
class BootState(State):
    def __init__(self, machine, synth, display, mode):
        self.machine = machine
        self.synth = synth
        self.display = display
        self.needs_initial_display = True
        self.boot_time = 20000 if mode == 'prod' else 2000

        self.logo = pygame.image.load('files/chp_logo.png').convert_alpha()
        self.logo_rect = self.logo.get_rect(center = (WIDTH / 2, HEIGHT / 2))
        self.text_boot = PRIMARY_FONT.render("Booting...", True, (255, 255, 255))
        self.text_boot_rect = self.text_boot.get_rect(center = (WIDTH / 2, HEIGHT / 2 - 40))
        self.text_sc = GCN_FONT.render("SOUNDCUBE", True, (255, 255, 255))
        self.text_sc_rect = self.text_sc.get_rect(center = (WIDTH / 2, HEIGHT / 2 + 30))

    def enter(self):
        self.display.off()
        self.synth_ok = self.synth.start()
        self.display.on()

    def update(self, dt):
        self.dt = dt
        if not self.synth_ok:
            self.machine.change(ShutdownState(self.machine, self.synth, self.display))
        if pygame.time.get_ticks() < self.boot_time:
            pass
        else:
            self.machine.change(RunState(self.machine, self.synth, self.display))

    def handle_input(self, action):
        pass 

    def render(self, screen, event_happened):
        if self.needs_initial_display or event_happened:
            screen.fill((0, 0, 0))
            pygame.draw.circle(
                screen,
                (40, 40, 40, 255),  # opaque
                (240 // 2, 240 // 2),
                120
            )
            dt = PRIMARY_FONT.render(str(pygame.time.get_ticks()), True, (255,255,255))
            # screen.blit(dt, (10,10))
            screen.blit(self.text_boot, self.text_boot_rect)
            screen.blit(self.logo, self.logo_rect)
            screen.blit(self.text_sc, self.text_sc_rect)
            if self.needs_initial_display:
                self.needs_initial_display = False
            # print("attempting to blit")
            return True
        else:
            return False

    def exit(self):
        self.synth.post_boot_init()
        

# -------------------------
# Base Run State
# -------------------------
class RunState(State):
    def __init__(self, machine, synth, display):
        self.machine = machine
        self.synth = synth
        self.display = display
        self.substate = "SELECT"
        self.needs_initial_display = True
        self.img_perf = pygame.image.load('files/perf.png').convert_alpha()
        self.img_sett = pygame.image.load('files/sett.png').convert_alpha()
        self.img_tri = pygame.image.load('files/tri.png').convert_alpha()
        self.img_breath = pygame.image.load('files/breath.png').convert_alpha()
        self.rect_breath = self.img_breath.get_rect(center=(45,72))
        self.font_breath = SECONDARY_FONT.render("(L)", True, 'white')
        self.rect_font_breath = self.font_breath.get_rect(center=(25,72))
        self.font_mono = SECONDARY_FONT.render("MONO", True, 'white')
        self.font_poly = SECONDARY_FONT.render("POLY", True, 'white')
        self.font_mono_rect = self.font_mono.get_rect(center=(45,92))
        self.font_poly_rect = self.font_poly.get_rect(center=(45,92))
        self.font_home = UNICODE_FONT.render("(⌂)", True, 'white')
        self.rect_home = self.font_home.get_rect(center=(20,90))
        self.imgs_tri = {
            "up": self.img_tri,
            "down": pygame.transform.flip(self.img_tri, flip_x=True, flip_y=False),
            "left": pygame.transform.rotate(self.img_tri, 90),
            "right": pygame.transform.rotate(self.img_tri, 270)
        }
        self.img_plus = pygame.image.load('files/plus.png').convert_alpha()
        self.rect_plus = self.img_plus.get_rect(center=(194,163))
        self.font_drums = SECONDARY_FONT.render("(Y)DRUM", True, 'white')
        self.rect_drums = self.font_drums.get_rect(center=(56,48))
        self.minus_pressed_at = None

    def enter(self):
        # Also runs when coming back from drum mode, so force a full repaint.
        self.needs_initial_display = True
        
    def handle_input(self, action: ConSignalMessage):
        if self.substate == "SELECT":
            self.handle_patch_select(action)
        elif self.substate == "SETTINGS":
            self.handle_settings(action)

    def handle_patch_select(self, action: ConSignalMessage):
        btn = action.c_button
        pressed = action.pressed
        if pressed:
            # Chords read the held set, so holding one stick click and then pressing
            # the other works rather than requiring both in the same event batch.
            if ConButton.L3 in action.held and ConButton.R3 in action.held:
                self.enter_update_mode()
            elif ConButton.LEFT in btn:
                self.synth.decrement_preset()
            elif ConButton.RIGHT in btn:
                self.synth.increment_preset()
            elif ConButton.A in btn:
                self.synth.enter_settings_mode()
                self.substate = "SETTINGS"
            elif ConButton.Y in btn:
                self.enter_drum_mode()
            elif ConButton.L in btn:
                self.synth.toggle_breathmode()
            elif ConButton.Z in btn:
                self.synth.panic_kill()
            elif ConButton.PLUS in btn:
                if self.synth.on_last_preset and not self.synth.presets_maxed_out:
                    self.synth.extend_preset()
                    self.synth.enter_settings_mode()
                    self.substate = "SETTINGS"
            elif ConButton.MINUS in btn or ConButton.SCRSH in btn:
                self.initiate_potential_shutdown()
        else:
            if ConButton.MINUS in btn:
                self.handle_shutdown()
            if ConButton.SCRSH in btn:
                self.handle_shutdown(True)

    def enter_update_mode(self):
        self.machine.change(UpdateState(self.machine, self.synth, self.display))

    def enter_drum_mode(self):
        if not self.synth.has_drum_kits():
            print("No drum kits available - skipping drum mode")
            return
        # Hand over this instance so returning is free: no reloading of the five
        # PNGs and text surfaces built in __init__.
        self.machine.change(
            PerformState(self.machine, self.synth, self.display, self))

    def handle_settings(self, action: ConSignalMessage):
        btn = action.c_button
        pressed = action.pressed
        if pressed:
            if ConButton.L3 in action.held and ConButton.R3 in action.held:
                self.enter_update_mode()
            elif ConButton.LEFT in btn:
                self.synth.decrement_program()
            elif ConButton.RIGHT in btn:
                self.synth.increment_program()
            elif ConButton.UP in btn:
                self.synth.increment_setting()
            elif ConButton.DOWN in btn:
                self.synth.decrement_setting()
            # elif ConButton.A in btn:
            #     self.synth.rotate_setting()
            elif ConButton.B in btn:
                self.synth.exit_settings_mode()
                self.substate = "SELECT"
            elif ConButton.X in btn:
                self.synth.rotate_sf2()
            elif ConButton.Y in btn:
                self.synth.rotate_setting()
            elif ConButton.PLUS in btn:
                self.synth.save_preset()
                self.synth.exit_settings_mode()
                self.substate = "SELECT"
            elif ConButton.L in btn:
                self.synth.toggle_breathmode()
            elif ConButton.HOME in btn:
                self.synth.toggle_mode()
            elif ConButton.Z in btn:
                self.synth.panic_kill()
            elif ConButton.MINUS in btn or ConButton.SCRSH in btn:
                self.initiate_potential_shutdown()
        else:
            if ConButton.MINUS in btn:
                self.handle_shutdown()
            if ConButton.SCRSH in btn:
                self.handle_shutdown(True)

    def initiate_potential_shutdown(self):
        self.minus_pressed_at = pygame.time.get_ticks()
        self.press_buffer = 3000
        # print(self.minus_pressed_at)
    
    def handle_shutdown(self, shutdown_system = False):
        if self.minus_pressed_at:
            if pygame.time.get_ticks() - self.minus_pressed_at > self.press_buffer:
                if not shutdown_system:
                    self.machine.change(ShutdownState(self.machine, self.synth, self.display))
                else:
                    perform_system_shutdown(self.machine, self.synth, self.display)
            else:
                self.minus_pressed_at = None
                print("didnt shutdown")

    def prerender(self):
        self.substate_icon_shown = self.img_perf if self.substate == 'SELECT' else self.img_sett
        self.preset_name_shown = self.synth.active_preset_name
        self.sf_icon_shown = self.synth.active_icon
        self.bank_num_shown = self.synth.active_bank
        self.inst_num_shown = self.synth.active_inst
        self.breath_mode_shown = self.synth.active_breathmode
        self.poly_mode_shown = self.synth.active_poly_mode
        self.extender_plus_shown = self.synth.on_last_preset and not self.synth.presets_maxed_out
        self.bg_color_shown = (40, 40, 40, 255) if self.substate == 'SELECT' else (60, 60, 60, 255)
    
    def render(self, screen, event_happened):
        if self.needs_initial_display or event_happened:
            self.prerender()
            screen.fill((40, 40, 40))
            # background
            pygame.draw.circle(
                screen,
                self.bg_color_shown, 
                (WIDTH / 2, HEIGHT / 2),
                WIDTH / 2
            )
            pygame.draw.circle(
                screen,
                (28, 28, 28, 255),
                (WIDTH / 2, 20),
                45
            )
            # foreground
            # show substate icon
            substate_logo = self.substate_icon_shown
            substate_rect = substate_logo.get_rect(center = (WIDTH / 2, HEIGHT / 2 - 89))
            screen.blit(substate_logo, substate_rect)
            # show preset num (same for both modes)
            color = PRESET_COLORS[self.synth.loaded_preset_num % len(PRESET_COLORS)]
            text_preset_num = PRESET_FONT.render(f"{self.synth.loaded_preset_num}", True, color)
            rect_preset_num = text_preset_num.get_rect(center=(WIDTH / 2, HEIGHT / 2))
            screen.blit(text_preset_num, rect_preset_num)
            # show preset name
            text_preset_name = PRIMARY_FONT.render(f"{self.preset_name_shown}", True, 'white')
            rect_preset_name = text_preset_name.get_rect(center=(WIDTH / 2, HEIGHT / 2 + 43))
            screen.blit(text_preset_name, rect_preset_name)
            # show preset info line 1
            text_preset_info_1 = SECONDARY_FONT.render(f"BANK {self.bank_num_shown}", True, 'white')
            rect_preset_info_1 = text_preset_info_1.get_rect(midright=(WIDTH / 2 - 10, HEIGHT / 2 + 75))
            screen.blit(text_preset_info_1, rect_preset_info_1)
            # show preset info line 2
            text_preset_info_2 = SECONDARY_FONT.render(f"PROG {self.inst_num_shown}", True, 'white')
            rect_preset_info_2 = text_preset_info_2.get_rect(midright=(WIDTH / 2 - 10, HEIGHT / 2 + 95))
            screen.blit(text_preset_info_2, rect_preset_info_2)
            # show icon 
            if self.breath_mode_shown:
                screen.blit(self.img_breath, self.rect_breath)
            if self.poly_mode_shown:
                screen.blit(self.font_poly, self.font_poly_rect)
            else:
                screen.blit(self.font_mono, self.font_mono_rect)
            game_icon = self.sf_icon_shown
            rect_game_icon = game_icon.get_rect(center = (WIDTH / 2 + 30, HEIGHT / 2 + 85))
            screen.blit(game_icon, rect_game_icon)
            left_arrow = self.imgs_tri['left']
            right_arrow = self.imgs_tri['right']
            screen.blit(self.font_breath, self.rect_font_breath)
            if self.substate == "SELECT":
                left_arrow_rect = left_arrow.get_rect(center=(WIDTH / 2 - 75, HEIGHT / 2))
                screen.blit(left_arrow, left_arrow_rect)
                right_arrow_rect = right_arrow.get_rect(center=(WIDTH / 2 + 75, HEIGHT / 2))
                screen.blit(right_arrow, right_arrow_rect)
                if self.synth.has_drum_kits():
                    screen.blit(self.font_drums, self.rect_drums)
                if self.extender_plus_shown:
                    screen.blit(self.img_plus, self.rect_plus)
            elif self.substate == 'SETTINGS':
                screen.blit(self.font_home, self.rect_home)
                left_arrow_rect = left_arrow.get_rect(center=(WIDTH / 2 - 75, HEIGHT / 2 + 43))
                screen.blit(left_arrow, left_arrow_rect)
                right_arrow_rect = right_arrow.get_rect(center=(WIDTH / 2 + 75, HEIGHT / 2 + 43))
                screen.blit(right_arrow, right_arrow_rect)
                text_save = PRIMARY_FONT.render("(+) SAVE", True, 'white')
                rect_save = text_save.get_rect(center=(WIDTH / 2 - 80, HEIGHT / 2))
                screen.blit(text_save, rect_save)
                text_settings_swap = SECONDARY_FONT.render("(B) BACK", True, 'white')
                rect_settings_swap = text_settings_swap.get_rect(center=(55,45))
                screen.blit(text_settings_swap,rect_settings_swap)
                text_sf2_change = SECONDARY_FONT.render("(X)", True, 'white')
                rect_sf2_change = text_sf2_change.get_rect(center=(181, 196))
                screen.blit(text_sf2_change, rect_sf2_change)
                fx_icon = self.synth.selected_fx_icon
                rect_fx_icon = fx_icon.get_rect(center=(190,65))
                screen.blit(fx_icon, rect_fx_icon)
                current_effect = self.synth.effects[self.synth.selected_effect_index]
                text_fx_name = SECONDARY_FONT.render(f"{current_effect.upper()}", True, 'white')
                rect_fx_name = text_fx_name.get_rect(center=(190,93))
                screen.blit(text_fx_name, rect_fx_name)
                text_fx_swap = SECONDARY_FONT.render("(Y)", True, 'white')
                rect_fx_swap = text_fx_swap.get_rect(center=(160,65))
                screen.blit(text_fx_swap, rect_fx_swap)
                pygame.draw.rect(screen, 'black', (180, 105, 20, 40))
                current_fx_val = round(self.synth.active_fx_chain[current_effect]['value'],1)
                current_fx_max = self.synth.fx_dict[current_effect]['rng'][1]
                fx_perc = round(current_fx_val / current_fx_max, 5)
                h = 36 * fx_perc
                y_pos = 143 - (h)
                pygame.draw.rect(screen, 'darkgreen', (182, y_pos, 16, h))
                text_fx_val = SECONDARY_FONT.render(f"{current_fx_val}", True, 'white')
                rect_fx_val = text_fx_val.get_rect(center=(190,125))
                screen.blit(text_fx_val, rect_fx_val)
            if self.needs_initial_display:
                self.needs_initial_display = False
            return True
        else:
            return False

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
        self.display.off()
        self.synth.stop()

    def handle_input(self, action):
        pass

    def update(self, dt):
        if not self.cleaned_up:
            pygame.quit()
            self.cleaned_up = True
            raise SystemExit

    def render(self, screen, event_happened):
        # Nothing to show; update() exits on the next tick anyway.
        return False

class UpdateState(State):
    def __init__(self, machine, synth, display):
        self.machine = machine
        self.synth = synth
        self.display = display
        self.first_update = True
        self.wifi_check_initiatied = False
        self.passed_wifi_check = None
        self.changes_check_started = False
        self.changes_available = None
        self.initiated_git_pull = False
        self.git_pull_succeeded = None
        # This screen advances on its own (wifi -> check -> result) with no input to
        # key off, so it tracks its own content signature to know when to redraw.
        self.last_render_signature = None

        if SOUNDCUBE_MODE == "prod":
            self.repo_dir = "/home/jacobrobertwest/soundcube"
        else:
            self.repo_dir = "/Users/jacob/Documents/SoundCube"
    
        self.version_text = SECONDARY_FONT.render(f"SOUNDCUBE v{SOUNDCUBE_VERSION}", True, 'black')
        self.version_text_rect = self.version_text.get_rect(center=(WIDTH / 2, HEIGHT / 2 - 70))
        self.connection_text = SECONDARY_FONT.render(f"Testing for Wifi", True, 'black')
        self.connection_text_rect = self.connection_text.get_rect(center=(WIDTH / 2, HEIGHT / 2 - 55))
        self.wifi_success_text = SECONDARY_FONT.render(f"Wifi Test Passed.", True, 'black')
        self.wifi_success_text_rect = self.wifi_success_text.get_rect(center=(WIDTH / 2, HEIGHT / 2 - 40))
        self.wifi_fail_text = SECONDARY_FONT.render(f"Wifi Test FAILED. Y to retry, MINUS to reboot.", True, 'black')
        self.wifi_fail_text_rect = self.wifi_fail_text.get_rect(center=(WIDTH / 2, HEIGHT / 2 - 40))
        self.changes_check_text = SECONDARY_FONT.render(f"Checking for latest updates...", True, 'black')
        self.changes_check_text_rect = self.changes_check_text.get_rect(center=(WIDTH / 2, HEIGHT / 2 - 25))
        self.changes_found_text = SECONDARY_FONT.render(f"Update available. Press A to proceed.", True, 'black')
        self.changes_found_text_rect = self.changes_found_text.get_rect(center=(WIDTH / 2, HEIGHT / 2 - 10))
        self.changes_not_found_text = SECONDARY_FONT.render(f"Already up to date. MINUS to reboot.", True, 'black')
        self.changes_not_found_text_rect = self.changes_not_found_text.get_rect(center=(WIDTH / 2, HEIGHT / 2 - 10))
        self.update_pass_text = SECONDARY_FONT.render(f"Update succeeded. MINUS to reboot.", True, 'black')
        self.update_pass_text_rect = self.update_pass_text.get_rect(center=(WIDTH / 2, HEIGHT / 2 + 5))
        self.update_fail_text = SECONDARY_FONT.render(f"Update failed. MINUS to reboot.", True, 'black')
        self.update_fail_text_rect = self.update_fail_text.get_rect(center=(WIDTH / 2, HEIGHT / 2 + 5))

    def enter(self):
        self.synth.stop()

    def handle_input(self, action):
        btn = action.c_button
        pressed = action.pressed
        if pressed:
            if self.passed_wifi_check is not None:
                if self.passed_wifi_check:
                    if self.changes_available:
                        if ConButton.A in btn:
                            self.git_pull_succeeded = self.git_pull()
                    if ConButton.MINUS in btn:
                        self.reboot()
                if self.passed_wifi_check == False:
                    if ConButton.Y in btn:
                        self.reset_wifi_test()
                    elif ConButton.MINUS in btn:
                        self.reboot()

    def reset_wifi_test(self):
        self.wifi_check_initiatied = False
        self.passed_wifi_check = None

    def reboot(self):
        if SOUNDCUBE_MODE == "dev":
            pygame.quit()
            print("sudo reboot")
            raise SystemExit
        else:
            pygame.quit()
            subprocess.run(["sudo", "reboot"])
        
    def update(self, dt):
        if self.first_update:
            self.first_update = False
            pass
        else:
            if not self.wifi_check_initiatied:
                self.wifi_check_initiatied = True
                self.passed_wifi_check = self.run_wifi_check()
            else:
                if self.passed_wifi_check:
                    if not self.changes_check_started:
                        self.changes_check_started = True
                        self.changes_available = self.check_for_changes()
    
    def check_for_changes(self):
        subprocess.run(
            ["git", "fetch", "origin", "main"],
            cwd=self.repo_dir,
            check=True,
            capture_output=True
        )
        result = subprocess.run(
            ["git", "rev-list", "HEAD..origin/main", "--count"],
            cwd=self.repo_dir,
            check=True,
            capture_output=True,
            text=True
        )
        return int(result.stdout.strip()) > 0
            
    def run_wifi_check(self):
        try:
            socket.create_connection(("8.8.8.8", 53), timeout=2)
            return True
        except OSError:
            return False
        
    def git_pull(self):
        try:
            subprocess.run(
                ["git", "pull", "origin", "main"],
                cwd=self.repo_dir,
                check=True,
                capture_output=True,
                text=True
            )
            return True
        except subprocess.SubprocessError:
            return False

    def render(self, screen, event_happened):
        signature = (self.passed_wifi_check, self.changes_available,
                     self.git_pull_succeeded)
        if signature == self.last_render_signature:
            return False
        self.last_render_signature = signature

        if True:
            screen.fill((40, 40, 40))
            # background
            pygame.draw.circle(
                screen,
                (255,255,255),
                (WIDTH / 2, HEIGHT / 2),
                WIDTH / 2
            )
            screen.blit(self.version_text, self.version_text_rect)
            screen.blit(self.connection_text, self.connection_text_rect)
            if self.passed_wifi_check:
                screen.blit(self.wifi_success_text, self.wifi_success_text_rect)
                screen.blit(self.changes_check_text, self.changes_check_text_rect)
                if self.changes_available == True:
                    screen.blit(self.changes_found_text, self.changes_found_text_rect)
                    if self.git_pull_succeeded == True:
                        screen.blit(self.update_pass_text, self.update_pass_text_rect)
                    elif self.git_pull_succeeded == False:
                        screen.blit(self.update_fail_text, self.update_fail_text_rect)
                elif self.changes_available == False:
                    screen.blit(self.changes_not_found_text, self.changes_not_found_text_rect)
            elif self.passed_wifi_check == False:
                screen.blit(self.wifi_fail_text, self.wifi_fail_text_rect)
            return True
        return False


# -------------------------
# Drum Performance State
# -------------------------
class PerformState(State):
    """Play a drum kit with the gamepad alone, no MIDI controller attached.

    Ten buttons are pads. The D-pad stays navigation, so kits and velocity change
    without leaving play. Deliberately does not redraw on a hit: a full frame is
    ~38ms of SPI clocking and would badly jitter the timing of everything after it.
    """
    tick_hz = 120           # ~8ms input granularity rather than 33ms
    uses_axis_edges = True  # one step per flick, not a repeat while deflected

    COL_X = (74, 166)
    ROW_Y = (106, 125, 144, 163, 182)
    ICON_Y = 32
    HEADER_Y = 68
    SUB_Y = 88
    FOOTER1_Y = 202
    FOOTER2_Y = 220
    HEADER_MAX_W = 196
    SAVED_MESSAGE_MS = 1500

    def __init__(self, machine, synth, display, return_state):
        self.machine = machine
        self.synth = synth
        self.display = display
        self.return_state = return_state
        self.substate = "PLAY"
        self.needs_initial_display = True
        self.dirty = False
        self.selected_pad = 0
        self.saved_at = None
        # note -> earliest tick at which its noteoff may be sent
        self.note_gate = {}
        # notes whose pad is released but whose minimum gate hasn't elapsed
        self.pending_release = set()
        # pad button -> the note it actually triggered, after resolution
        self.sounding = {}
        self.minus_pressed_at = None
        self.press_buffer = 3000

        self.text_cache = {}
        self.pad_surfaces = []
        self.rebuild_labels()

    def enter(self):
        self.synth.enter_drum_mode()
        self.rebuild_labels()

    def exit(self):
        # Nothing may be left hanging when the melodic patch comes back.
        self.all_notes_off()
        self.synth.exit_drum_mode()

    # -------------------------
    # Label cache
    # -------------------------
    def _text(self, message, color='white', font=None):
        """Font rendering is far too slow to do per frame, and pad labels only
        change on a kit or binding change."""
        font = font or SECONDARY_FONT
        key = (id(font), message, str(color))
        surface = self.text_cache.get(key)
        if surface is None:
            surface = font.render(message, True, color)
            self.text_cache[key] = surface
        return surface

    def _fit_header(self, message):
        """Kit names run to 20 characters. Drop to the smaller face rather than
        cutting a word in half, and only trim as a last resort."""
        for font in (PRIMARY_FONT, SECONDARY_FONT):
            surface = self._text(message, 'white', font)
            if surface.get_width() <= self.HEADER_MAX_W:
                return surface
        trimmed = message
        while len(trimmed) > 4:
            trimmed = trimmed[:-1]
            surface = self._text(trimmed + '.', 'white', SECONDARY_FONT)
            if surface.get_width() <= self.HEADER_MAX_W:
                return surface
        return self._text(message[:8], 'white', SECONDARY_FONT)

    def rebuild_labels(self):
        kit = self.synth.active_drum_kit()
        total = len(self.synth.drum_kits)
        index = self.synth.selected_kit_index + 1 if total else 0

        self.header = self._fit_header(
            (kit['name'] if kit else 'NO KITS').upper())
        self.header_rect = self.header.get_rect(center=(WIDTH / 2, self.HEADER_Y))
        self.subheader = self._text(f"KIT {index}/{total}")
        self.subheader_rect = self.subheader.get_rect(center=(WIDTH / 2, self.SUB_Y))
        self.icon = self.synth.drum_kit_icon()

        self.pad_surfaces = []
        for i, button in enumerate(PAD_BUTTONS):
            # Show what will actually sound, not what is stored: a binding can
            # point at a note this kit doesn't populate.
            note = self.synth.resolve_drum_note(self.synth.pad_note(button.name))
            surface = self._text(f"{button.name}:{drum_label(note, short=True)}")
            centre = (self.COL_X[i // len(self.ROW_Y)], self.ROW_Y[i % len(self.ROW_Y)])
            self.pad_surfaces.append((surface, surface.get_rect(center=centre)))
        self.dirty = True

    # -------------------------
    # Input
    # -------------------------
    def handle_input(self, action: ConSignalMessage):
        buttons = action.c_button
        if not buttons:
            return
        button = buttons[0]

        if SOUNDCUBE_DEBUG:
            kit = self.synth.active_drum_kit()
            print(f"[PAD] {button.name:5s} {'DOWN' if action.pressed else 'up  '} "
                  f"{self.substate:5s} kit={self.synth.selected_kit_index}"
                  f" '{kit['name'] if kit else '-'}' src={action.c_type.name}")

        if action.pressed:
            if button in PAD_BUTTONS:
                self.hit_pad(button)
            elif button in (ConButton.LEFT, ConButton.RIGHT,
                            ConButton.UP, ConButton.DOWN):
                self.handle_direction(button)
            elif button == ConButton.PLUS:
                self.handle_plus()
            elif button == ConButton.HOME:
                self.handle_home()
            elif button in (ConButton.MINUS, ConButton.SCRSH):
                self.initiate_potential_shutdown()
        else:
            if button in PAD_BUTTONS:
                self.release_pad(button)
            elif button == ConButton.MINUS:
                self.handle_shutdown()
            elif button == ConButton.SCRSH:
                self.handle_shutdown(True)

    def hit_pad(self, button):
        note = self.synth.resolve_drum_note(self.synth.pad_note(button.name))
        if self.substate == "EDIT":
            index = PAD_BUTTONS.index(button)
            if index != self.selected_pad:
                self.selected_pad = index
                self.dirty = True
        self.trigger(note)
        self.sounding[button] = note

    def trigger(self, note):
        self.note_gate[note] = pygame.time.get_ticks() + DRUM_MIN_GATE_MS
        self.pending_release.discard(note)
        self.synth.drum_noteon(note)

    def release_pad(self, button):
        note = self.sounding.pop(button, None)
        if note is None:
            return
        # Two pads can be bound to the same drum; don't cut it while one is held.
        if note in self.sounding.values():
            return
        if pygame.time.get_ticks() >= self.note_gate.get(note, 0):
            self.send_noteoff(note)
        else:
            # Too soon - update() will send it once the gate elapses, so a fast
            # tap isn't cut off mid-transient.
            self.pending_release.add(note)

    def send_noteoff(self, note):
        self.synth.drum_noteoff(note)
        self.note_gate.pop(note, None)
        self.pending_release.discard(note)

    def all_notes_off(self):
        for note in list(self.note_gate):
            self.synth.drum_noteoff(note)
        self.note_gate.clear()
        self.pending_release.clear()
        self.sounding.clear()

    def change_kit(self, delta):
        # A select while notes are ringing would leave them hanging on the old kit.
        self.all_notes_off()
        kit = self.synth.cycle_drum_kit(delta)
        if SOUNDCUBE_DEBUG:
            print(f"[KIT] changed by {delta:+d} -> #{self.synth.selected_kit_index} "
                  f"'{kit['name'] if kit else '-'}' (sf2 {kit['sf2'] if kit else '-'})")
        self.rebuild_labels()

    def handle_direction(self, button):
        """In PLAY, left/right swaps kit and up/down sets velocity.

        In EDIT every direction moves through the kit's drums instead. Reaching for
        left/right to pick the next drum must not swap the whole kit out from under
        you - which is precisely what it used to do.
        """
        if self.substate == "EDIT":
            forward = button in (ConButton.RIGHT, ConButton.UP)
            self.shift_selected_note(1 if forward else -1)
            return
        if button == ConButton.LEFT:
            self.change_kit(-1)
        elif button == ConButton.RIGHT:
            self.change_kit(1)
        else:
            self.synth.adjust_velocity(
                DRUM_VELOCITY_STEP if button == ConButton.UP else -DRUM_VELOCITY_STEP)
            self.dirty = True

    def shift_selected_note(self, direction):
        """Walk the selected pad through the notes this kit actually populates,
        so the editor never offers a silent choice."""
        kit = self.synth.active_drum_kit()
        if kit is None:
            return
        notes = kit['notes']
        button = PAD_BUTTONS[self.selected_pad]
        current = self.synth.resolve_drum_note(self.synth.pad_note(button.name))
        try:
            index = notes.index(current)
        except ValueError:
            index = 0
        note = notes[(index + direction) % len(notes)]
        self.synth.set_pad_note(button.name, note)
        self.rebuild_labels()
        self.trigger(note)
        self.pending_release.add(note)  # audition, released by update()

    def handle_plus(self):
        if self.substate == "PLAY":
            self.substate = "EDIT"
        else:
            if self.synth.save_kits():
                self.saved_at = pygame.time.get_ticks()
        self.dirty = True

    def handle_home(self):
        if self.substate == "EDIT":
            self.substate = "PLAY"
            self.dirty = True
        else:
            self.machine.change(self.return_state)

    def initiate_potential_shutdown(self):
        self.minus_pressed_at = pygame.time.get_ticks()
        self.press_buffer = 3000

    def handle_shutdown(self, shutdown_system=False):
        if self.minus_pressed_at:
            if pygame.time.get_ticks() - self.minus_pressed_at > self.press_buffer:
                if not shutdown_system:
                    self.machine.change(
                        ShutdownState(self.machine, self.synth, self.display))
                else:
                    perform_system_shutdown(self.machine, self.synth, self.display)
            else:
                self.minus_pressed_at = None

    def update(self, dt):
        now = pygame.time.get_ticks()
        if self.pending_release:
            for note in [n for n in self.pending_release
                         if now >= self.note_gate.get(n, 0)]:
                self.send_noteoff(note)
        if self.saved_at and now - self.saved_at >= self.SAVED_MESSAGE_MS:
            self.saved_at = None
            self.dirty = True

    # -------------------------
    # Render
    # -------------------------
    def render(self, screen, event_happened):
        # event_happened is ignored on purpose. A pad hit is an event but must not
        # cost a full-frame SPI push; only real content changes redraw.
        if not (self.needs_initial_display or self.dirty):
            return False

        editing = self.substate == "EDIT"
        screen.fill((0, 0, 0))
        pygame.draw.circle(
            screen,
            (52, 44, 30) if editing else (32, 50, 38),
            (WIDTH / 2, HEIGHT / 2),
            WIDTH / 2
        )

        if self.icon is not None:
            screen.blit(self.icon, self.icon.get_rect(center=(WIDTH / 2, self.ICON_Y)))
        screen.blit(self.header, self.header_rect)
        screen.blit(self.subheader, self.subheader_rect)

        for i, (surface, rect) in enumerate(self.pad_surfaces):
            if editing and i == self.selected_pad:
                # Outline rather than a fill, so the white label stays readable.
                pygame.draw.rect(screen, (235, 200, 60), rect.inflate(10, 6),
                                 width=2, border_radius=4)
            screen.blit(surface, rect)

        if editing:
            button = PAD_BUTTONS[self.selected_pad]
            note = self.synth.resolve_drum_note(self.synth.pad_note(button.name))
            # The angle brackets advertise that the directions move through drums.
            line_one = self._text(f"< #{note} {drum_label(note)} >"[:26])
            line_two = self._text("(+)SAVE  (H)BACK")
        else:
            line_one = self._text(f"VEL {self.synth.drum_velocity}")
            line_two = self._text("(+)EDIT  (H)EXIT")
        if self.saved_at:
            line_two = self._text("SAVED", (235, 200, 60))

        screen.blit(line_one, line_one.get_rect(center=(WIDTH / 2, self.FOOTER1_Y)))
        screen.blit(line_two, line_two.get_rect(center=(WIDTH / 2, self.FOOTER2_Y)))

        self.needs_initial_display = False
        self.dirty = False
        return True


