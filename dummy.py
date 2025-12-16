# -------------------------
# Placeholder Synth
# -------------------------
class DummySynth:
    def start(self):
        print("Synth starting...")
        return True  # simulate success

    def stop(self):
        print("Synth stopping...")

    def load_patch(self, patch_index):
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