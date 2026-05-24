import pygame
from settings import *
# -------------------------
# Base State and StateMachine
# -------------------------
class State:
    def enter(self): pass
    def exit(self): pass
    def handle_input(self, action: ConSignalMessage): pass
    def update(self, dt): pass
    def render(self, screen, event_happened): pass

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
        self.minus_pressed_at = None
        
    def handle_input(self, action: ConSignalMessage):
        if self.substate == "SELECT":
            self.handle_patch_select(action.c_button, action.pressed)
        elif self.substate == "SETTINGS":
            self.handle_settings(action.c_button, action.pressed)

    def handle_patch_select(self, btn: list[ConButton], pressed):
        if pressed:
            if ConButton.L3 in btn and ConButton.R3 in btn:
                self.enter_update_mode()
            elif ConButton.LEFT in btn:
                self.synth.decrement_preset()
            elif ConButton.RIGHT in btn:
                self.synth.increment_preset()
            elif ConButton.A in btn:
                self.synth.enter_settings_mode()
                self.substate = "SETTINGS"
            elif ConButton.L in btn:
                self.synth.toggle_breathmode()
            elif ConButton.Z in btn:
                self.synth.panic_kill()
            elif ConButton.MINUS in btn or ConButton.SCRSH in btn:
                self.initiate_potential_shutdown()
        else:
            if ConButton.MINUS in btn:
                self.handle_shutdown()
            if ConButton.SCRSH in btn:
                self.handle_shutdown(True)

    def enter_update_mode(self):
        self.machine.change(UpdateState(self.machine, self.synth, self.display))

    def handle_settings(self, btn: list[ConButton], pressed):
        if pressed:
            if ConButton.L3 in btn and ConButton.R3 in btn:
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
                    self.display.off()
                    os.system("sudo shutdown -h now")
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


