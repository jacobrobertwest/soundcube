import subprocess
import os
import threading
import sf2utils

class Synth:
    def start(self):
        print("Synth starting...")
        cmd = [
        "fluidsynth",
        "-a", "alsa", 
        "-o", "midi.autoconnect=True",
        "files/bootup.mid"
        ]
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
        return True
        
    def send_command(self, command):
        self.fs_terminal.stdin.write(command + "\n")
        self.fs_terminal.stdin.flush()

    def stop(self):
        print("Synth stopping...")
        self.fs_terminal.terminate()
        self.fs_terminal.wait(timeout=2)

    def load_patch(self, patch_index):
        self.send_command(f"prog 0 {patch_index}") 
        print(f"Loaded patch {patch_index + 1}")

    def save_patch(self, patch_index):
        print(f"Saved patch {patch_index + 1}")

    def volume_up(self):
        print("Volume up")

    def volume_down(self):
        print("Volume down")
