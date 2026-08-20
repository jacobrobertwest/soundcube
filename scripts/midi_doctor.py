# -------------------------
# MIDI routing diagnostic
# -------------------------
# Run this ON THE DEVICE while both controllers are plugged in and the app is
# running, then send back the whole output:
#
#   python3 scripts/midi_doctor.py
#
# It only reads; nothing is changed.
import os
import subprocess
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
import midi_devices


def run(label, args):
    print(f"\n----- {label}: {' '.join(args)} -----")
    try:
        r = subprocess.run(args, capture_output=True, text=True, timeout=10)
        print(r.stdout.rstrip() or "(no stdout)")
        if r.stderr.strip():
            print("stderr:", r.stderr.strip())
        print(f"(exit {r.returncode})")
    except FileNotFoundError:
        print("!! COMMAND NOT FOUND - this is likely the problem")
    except Exception as e:
        print(f"!! {type(e).__name__}: {e}")


print("=" * 70)
print("SOUNDCUBE MIDI ROUTING DIAGNOSTIC")
print("=" * 70)

print("\n----- raw /proc/asound/seq/clients -----")
try:
    with open("/proc/asound/seq/clients") as f:
        raw = f.read()
    print(raw.rstrip())
except OSError as e:
    print(f"!! cannot read: {e}")
    raw = ""

print("\n----- what SoundCube sees -----")
print("controllers detected:")
for p in midi_devices.input_ports(raw):
    print(f"    {p.address:8s} {p.client_name!r} port={p.port_name!r} flags={p.flags}")
print("fluidsynth input ports:")
for p in midi_devices.fluid_ports(raw):
    print(f"    {p.address:8s} {p.port_name!r} flags={p.flags}")
print(f"device_count() -> {midi_devices.device_count()}")
print(f"describe()     -> {midi_devices.describe()}")

fl = midi_devices.fluid_ports(raw)
if len(fl) < 2:
    print("\n!! fluidsynth exposes fewer than 2 input ports.")
    print("!! Without a second port there is nowhere to route controller 2.")
    print("!! Check that fluidsynth was started with synth.midi-channels=32")
    print("!! and that the MIDI driver is alsa_seq.")

run("connections", ["aconnect", "-l"])
run("readable clients", ["aconnect", "-i"])
run("writable clients", ["aconnect", "-o"])
run("aconnect location", ["which", "aconnect"])
run("fluidsynth version", ["fluidsynth", "--version"])
run("running fluidsynth", ["pgrep", "-af", "fluidsynth"])
print("\n" + "=" * 70)
