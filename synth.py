import subprocess
import threading
from settings import *

class Synth:
    def start(self):
        print("Synth starting...")
        self.sf_folder = 'files/sf2'
        self.icon_folder = 'files/sf2_icon'
        self.meta_folder = 'files/sf2_meta'
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
        # self.run_synth() #uncomment in prod
        return True
    
    def run_synth(self):

        # Build the command
        cmd = [
            "fluidsynth",
            "-a", "alsa",
            "-o", "midi.autoconnect=True"
        ]
        cmd.extend(self.sf2_files)
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
        self.loaded_preset = self.presets[str(self.loaded_preset_num)]
        self.active_sf2 = self.loaded_preset["sf2"]
        self.active_bank = self.loaded_preset["bank"]
        self.active_inst = self.loaded_preset["inst"]
        self.enforce_active_elements()

    def enforce_active_elements(self):
        self.active_sf2_meta = self.meta_maps[self.active_sf2]
        self.active_preset_name = self.active_sf2_meta[(self.active_bank, self.active_inst)]
        self.active_icon = self.bank_icons[self.active_sf2]
        self.send_command(f"select 0 {self.active_sf2} {self.active_bank} {self.active_inst}")

    def increment_preset(self):
        new_loaded_preset_num = (self.loaded_preset_num % self.num_presets) + 1
        if new_loaded_preset_num > self.num_presets:
            new_loaded_preset_num = 1
        self.handle_preset_change(new_loaded_preset_num)

    def decrement_preset(self):
        new_loaded_preset_num = (self.loaded_preset_num - 2) % self.num_presets + 1
        self.handle_preset_change(new_loaded_preset_num)

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
        if new_sf2_index >= len(self.sf2_files):
            new_sf2_index = 0
        self.active_sf2 = new_sf2_index
        self.active_sf2_meta = self.meta_maps[self.active_sf2]
        keys = list(self.active_sf2_meta.keys())
        bank, inst = keys[0]
        self.active_bank = bank
        self.active_inst = inst
        self.enforce_active_elements()

    def rotate_setting(self):
        pass

    def save_preset(self):
        self.presets[str(self.loaded_preset_num)]['sf2'] = self.active_sf2
        self.presets[str(self.loaded_preset_num)]['bank'] = self.active_bank
        self.presets[str(self.loaded_preset_num)]['inst'] = self.active_inst
        with open(self.presets_file, "w", encoding="utf-8") as f:
            json.dump(self.presets, f, indent=2, separators=(",", ": "))
        print('Saved preset')

    def exit_settings_mode(self):
        print('Exiting settings mode')
        self.handle_preset_change(self.loaded_preset_num)

    def stop(self):
        print("Synth stopping...")
        if self.fs_terminal:
            self.fs_terminal.terminate()
            self.fs_terminal.wait(timeout=2)

    def volume_up(self):
        print("Volume up")

    def volume_down(self):
        print("Volume down")
