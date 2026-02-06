import subprocess
import threading
from settings import *

class Synth:
    def start(self):
        print("Synth starting...")
        self.sf_folder = 'files/sf2'
        self.icon_folder = 'files/sf2_icon'
        self.meta_folder = 'files/sf2_meta'
        self.fx_icon_folder = 'files/fx_icon'
        self.presets_file = 'files/presets.json'
        self.load_meta_maps()
        self.banks = sorted(
            f for f in os.listdir(self.sf_folder)
            if f.endswith(".sf2")
        )
        self.bank_icon_files =  sorted(
            f for f in os.listdir(self.icon_folder)
            if f.endswith(".png")
        )
        self.bank_icons = [pygame.image.load(os.path.join(self.icon_folder, f)).convert_alpha() for f in self.bank_icon_files]

        with open(self.presets_file, "r") as f:
            self.presets = json.load(f)

        self.num_presets = len(self.presets)
        self.sf2_files = sorted(glob.glob(os.path.join("files", "sf2", "*.sf2")))
        self.fs_terminal = None
        self.fx_dict = FX_LIBRARY
        self.effects = list(self.fx_dict.keys())
        self.fx_icon_files =  sorted(
            f for f in os.listdir(self.fx_icon_folder)
            if f.endswith(".png")
        )
        self.fx_icons = [pygame.image.load(os.path.join(self.fx_icon_folder, f)).convert_alpha() for f in self.fx_icon_files]
        self.selected_effect_index = 0
        self.selected_fx_icon = self.fx_icons[self.selected_effect_index]
        self.selected_fx_meta_map = self.fx_dict[self.effects[self.selected_effect_index]]
        self.run_synth() #uncomment in prod
        return True
    
    def run_synth(self):
        # Build the command
        cmd = [
            "fluidsynth",
            "-a", "alsa",
            "-o", "midi.autoconnect=True"
        ]
        cmd.append(self.sf2_files[0])
        cmd.append("files/bootup.mid")

        # start the subprocess terminal
        self.fs_terminal = subprocess.Popen(
            cmd,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        
        def watch_output():
            for line in self.fs_terminal.stdout:
                print("[FLUIDSYNTH]", line.strip())
                
        def watch_errors():
            for line in self.fs_terminal.stderr:
                print("[FS ERROR]", line.strip())
                
        threading.Thread(target=watch_output, daemon=True).start()
        threading.Thread(target=watch_errors, daemon=True).start()
    
    # post boot up 
    def post_boot_init(self):
        for f in self.sf2_files[1:]:
            self.send_command(f"load {f}")
        self.send_command("fonts")
        self.send_command("set synth.polyphony 8")
        self.handle_preset_change(1)
    
    # send command to subprocess terminal running fluidsynth
    def send_command(self, command):
        if self.fs_terminal:
            self.fs_terminal.stdin.write(command + "\n")
            self.fs_terminal.stdin.flush()
        else:
            print(f'[FLUIDSYNTH] {command}')

    # load sf2 metadata map from JSON file
    def load_meta_maps(self):
        self.meta_maps = []
        for filename in sorted(os.listdir(self.meta_folder)):
            if not filename.endswith(".json"):
                continue

            path = os.path.join(self.meta_folder, filename)

            with open(path, "r") as f:
                raw_map = json.load(f)

            preset_map = {
                tuple(map(int, key.split(":"))): name
                for key, name in raw_map.items()
            }

            self.meta_maps.append(preset_map)
    
    # --- PERFORMANCE / SELECT MODE -----
    def handle_preset_change(self, index):
        self.loaded_preset_num = index
        self.loaded_preset = deepcopy(self.presets[str(self.loaded_preset_num)])
        self.active_sf2 = self.loaded_preset["sf2"]
        self.active_bank = self.loaded_preset["bank"]
        self.active_inst = self.loaded_preset["inst"]
        self.active_breathmode = self.loaded_preset["breathmode"]
        self.active_poly_mode = self.loaded_preset["poly_mode"]
        if "fx" not in self.loaded_preset:
            self.loaded_preset['fx'] = {}
            for effect in self.fx_dict:
                self.loaded_preset['fx'][effect] = {}
                self.loaded_preset['fx'][effect]['value'] = self.fx_dict[effect]['def']
                self.loaded_preset['fx'][effect]['params'] = None
                # if self.fx_dict[effect]['params'] is not None:
                #     self.loaded_preset['fx'][effect]['params'] = {}
                #     for param in self.fx_dict[effect]['params']:
                #         self.loaded_preset['fx'][effect]['params'][param] = self.fx_dict[effect]['params'][param]['def']
            # print(self.loaded_preset['fx'])
        self.active_fx_chain = deepcopy(self.loaded_preset['fx'])
        if self.active_poly_mode:
            self.send_command("resetbasicchannels")
            self.send_command("setbasicchannels 0 2 1")
        else:
            self.send_command("resetbasicchannels")
            self.send_command("setbasicchannels 0 3 1")
        if self.active_breathmode:
            self.send_command("setbreathmode 0 1 1 0")
        else:
            self.send_command("setbreathmode 0 0 0 0")
        self.enforce_active_elements()
        self.enforce_fx()

    def enforce_fx(self):
        for effect in self.active_fx_chain:
            self.send_command(self.fx_dict[effect]['cmd'].format(val=self.active_fx_chain[effect]['value']))
            # if self.active_fx_chain[effect]['params'] is not None:
            #     for param in self.active_fx_chain[effect]['params']:
            #         self.send_command(self.fx_dict[effect]['params'][param]['cmd'].format(val=self.active_fx_chain[effect]['params'][param]))

    def enforce_active_elements(self):
        self.active_sf2_meta = self.meta_maps[self.active_sf2 - 1]
        self.active_preset_name = self.active_sf2_meta[(self.active_bank, self.active_inst)]
        self.active_icon = self.bank_icons[self.active_sf2 - 1]
        self.send_command(f"select 0 {self.active_sf2} {self.active_bank} {self.active_inst}")

    def increment_preset(self):
        new_loaded_preset_num = (self.loaded_preset_num % self.num_presets) + 1
        if new_loaded_preset_num > self.num_presets:
            new_loaded_preset_num = 1
        self.handle_preset_change(new_loaded_preset_num)

    def decrement_preset(self):
        new_loaded_preset_num = (self.loaded_preset_num - 2) % self.num_presets + 1
        self.handle_preset_change(new_loaded_preset_num)

    def panic_kill(self):
        # control change | channel 0 | cc123 (kill all notes) | value (not used for this CC, but required)
        self.send_command("cc 0 123 0")

    # --- SETTINGS MODE -----
    def enter_settings_mode(self):
        print("Entering settings mode")

    def increment_program(self):
        keys = list(self.active_sf2_meta.keys())
        current_key = (self.active_bank, self.active_inst)
        index = keys.index(current_key)
        next_prog = keys[(index + 1) % len(keys)]
        bank, inst = next_prog
        self.active_bank = bank
        self.active_inst = inst
        self.enforce_active_elements()

    def decrement_program(self):
        keys = list(self.active_sf2_meta.keys())
        current_key = (self.active_bank, self.active_inst)
        index = keys.index(current_key)
        next_prog = keys[(index - 1) % len(keys)]
        bank, inst = next_prog
        self.active_bank = bank
        self.active_inst = inst
        self.enforce_active_elements()

    def rotate_sf2(self):
        new_sf2_index = self.active_sf2 + 1
        if new_sf2_index > len(self.sf2_files):
            new_sf2_index = 1
        self.active_sf2 = new_sf2_index
        self.active_sf2_meta = self.meta_maps[self.active_sf2 - 1]
        keys = list(self.active_sf2_meta.keys())
        bank, inst = keys[0]
        self.active_bank = bank
        self.active_inst = inst
        self.enforce_active_elements()

    def rotate_setting(self):
        new_settings_index = self.selected_effect_index + 1
        if new_settings_index >= len(self.effects):
            new_settings_index = 0
        self.selected_effect_index = new_settings_index
        self.selected_fx_icon = self.fx_icons[self.selected_effect_index]
        self.selected_fx_meta_map = self.fx_dict[self.effects[self.selected_effect_index]]

    def increment_setting(self):
        print("Setting up")
        new_setting_val = round(self.active_fx_chain[self.effects[self.selected_effect_index]]['value'] + self.selected_fx_meta_map['incr'],1)
        if new_setting_val > self.selected_fx_meta_map['rng'][1]:
            new_setting_val = self.selected_fx_meta_map['rng'][1]
        self.send_command(self.selected_fx_meta_map['cmd'].format(val=new_setting_val))
        self.active_fx_chain[self.effects[self.selected_effect_index]]['value'] = new_setting_val

    def decrement_setting(self):
        print("Setting down")
        new_setting_val = round(self.active_fx_chain[self.effects[self.selected_effect_index]]['value'] - self.selected_fx_meta_map['incr'],1)
        if new_setting_val < self.selected_fx_meta_map['rng'][0]:
            new_setting_val = self.selected_fx_meta_map['rng'][0]
        self.send_command(self.selected_fx_meta_map['cmd'].format(val=new_setting_val))
        self.active_fx_chain[self.effects[self.selected_effect_index]]['value'] = new_setting_val
    
    def toggle_breathmode(self):
        self.active_breathmode = not self.active_breathmode
        if self.active_breathmode:
            self.send_command("setbreathmode 0 1 1 0")
        else:
            self.send_command("setbreathmode 0 0 0 0")
    
    def toggle_mode(self):
        self.active_poly_mode = not self.active_poly_mode
        if self.active_poly_mode:
            self.send_command("resetbasicchannels")
            self.send_command("setbasicchannels 0 2 1")
        else:
            self.send_command("resetbasicchannels")
            self.send_command("setbasicchannels 0 3 1")
        

    def save_preset(self):
        self.presets[str(self.loaded_preset_num)]['sf2'] = self.active_sf2
        self.presets[str(self.loaded_preset_num)]['bank'] = self.active_bank
        self.presets[str(self.loaded_preset_num)]['inst'] = self.active_inst
        self.presets[str(self.loaded_preset_num)]['breathmode'] = self.active_breathmode
        self.presets[str(self.loaded_preset_num)]['poly_mode'] = self.active_poly_mode
        self.presets[str(self.loaded_preset_num)]['fx'] = deepcopy(self.active_fx_chain)
        with open(self.presets_file, "w", encoding="utf-8") as f:
            json.dump(self.presets, f, indent=2, separators=(",", ": "))
        print('Saved preset')

    def exit_settings_mode(self):
        print('Exiting settings mode')
        self.selected_effect_index = 0
        self.selected_fx_icon = self.fx_icons[self.selected_effect_index]
        self.selected_fx_meta_map = self.fx_dict[self.effects[self.selected_effect_index]]
        self.handle_preset_change(self.loaded_preset_num)

    def stop(self):
        print("Synth stopping...")
        if self.fs_terminal:
            self.fs_terminal.terminate()
            self.fs_terminal.wait(timeout=2)
