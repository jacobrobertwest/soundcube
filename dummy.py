# -------------------------
# Placeholder Synth
# -------------------------
import os
import json
from settings import *

class DummySynth:
    def start(self):
        print("Synth starting...")
        self.sf_folder = 'files/sf2'
        self.icon_folder = 'files/sf2_icon'
        self.meta_folder = 'files/sf2_meta'
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

        with open("files/presets.json", "r") as f:
            self.presets = json.load(f)
        self.handle_preset_change(1)
        return True
    
    def load_meta_maps(self):
        self.meta_maps = []
        for filename in sorted(os.listdir(self.meta_folder)):
            if not filename.endswith(".json"):
                continue

            path = os.path.join(self.meta_folder, filename)

            with open(path, "r") as f:
                raw_map = json.load(f)

            # Convert string keys back to tuple keys
            preset_map = {
                tuple(map(int, key.split(":"))): name
                for key, name in raw_map.items()
            }

            self.meta_maps.append(preset_map)
    
    def handle_preset_change(self, index):
        self.loaded_preset_num = index
        self.loaded_preset = self.presets[str(self.loaded_preset_num)]
        self.loaded_sf2 = self.loaded_preset["sf2"]
        self.loaded_sf2_meta = self.meta_maps[self.loaded_sf2]
        self.loaded_bank = self.loaded_preset["bank"]
        self.loaded_inst = self.loaded_preset["inst"]
        self.loaded_preset_name = self.loaded_sf2_meta[(self.loaded_bank, self.loaded_inst)]
        self.loaded_icon = self.bank_icons[self.loaded_bank]
        
    def send_command(self, command):
        pass

    def stop(self):
        print("Synth stopping...")

    def load_patch(self, patch_index):
        self.send_command(f"prog 0 {patch_index}") 
        print(f"Loaded patch {patch_index + 1}")

    def save_patch(self, patch_index):
        print(f"Saved patch {patch_index + 1}")

    def volume_up(self):
        print("Volume up")

    def volume_down(self):
        print("Volume down")

# -------------------------
# Placeholder Display
# -------------------------
class DummyDisplay:
    def on(self):
        print("Display ON")

    def off(self):
        print("Display OFF")

    def show_message(self, msg):
        print(f"Display message: {msg}")
