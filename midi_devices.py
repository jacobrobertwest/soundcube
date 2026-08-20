# -------------------------
# MIDI input device discovery and routing
# -------------------------
# fluidsynth's midi.autoconnect merges every MIDI input into one stream, and its
# router can see channel numbers but not which device sent a message. So two
# controllers both transmitting on MIDI channel 1 would drive the same voice.
#
# The separation instead uses fluidsynth's multi-port behaviour: with
# synth.midi-channels=32 the ALSA sequencer driver creates two input ports, and
# port N maps onto synth channels N*16 .. N*16+15. Wiring the second controller to
# port 1 puts it on channel 16, independent of what channel it transmits on.
#
# Everything ALSA-specific is isolated here. Off Linux (a mac dev machine) discovery
# returns nothing and routing is a no-op, so the rest of the app behaves as
# single-controller. SOUNDCUBE_FAKE_MIDI_DEVICES=n simulates n devices for testing.
import os
import re
import subprocess

SEQ_CLIENTS = "/sys/class/sound/seq/clients"   # not used; see PROC_CLIENTS
PROC_CLIENTS = "/proc/asound/seq/clients"

# Kernel sequencer clients that are never a player's controller.
IGNORED_CLIENT_NAMES = ("system", "midi through", "announce", "timer")

_CLIENT_RE = re.compile(r'^Client\s+(\d+)\s*:\s*"([^"]*)"\s*\[([^\]]*)\]')
_PORT_RE = re.compile(r'^\s+Port\s+(\d+)\s*:\s*"([^"]*)"\s*\(([^)]*)\)')
_ADDR_RE = re.compile(r'^\d+:\d+$')


class MidiPort:
    def __init__(self, client, port, client_name, port_name, flags,
                 connecting_to=None):
        self.client = client
        self.port = port
        self.client_name = client_name
        self.port_name = port_name
        self.flags = flags
        self.connecting_to = list(connecting_to or [])

    @property
    def address(self):
        return f"{self.client}:{self.port}"

    def __repr__(self):
        return f"<MidiPort {self.address} {self.client_name!r} flags={self.flags}>"

    def __eq__(self, other):
        return isinstance(other, MidiPort) and self.address == other.address

    def __hash__(self):
        return hash(self.address)


def fake_device_count():
    """Test/dev override. Returns None when unset.

    The value is either a count, or a path to a file containing one. The file form
    lets the count change while the app is running, so plugging and unplugging a
    second controller can be simulated live:

        SOUNDCUBE_FAKE_MIDI_DEVICES=/tmp/midi_count python3 main.py
        echo 2 > /tmp/midi_count     # second controller appears
        echo 1 > /tmp/midi_count     # and goes away again
    """
    raw = os.getenv("SOUNDCUBE_FAKE_MIDI_DEVICES")
    if raw is None:
        return None
    raw = raw.strip()
    if not raw.isdigit():
        try:
            with open(raw, "r", encoding="utf-8") as f:
                raw = f.read().strip()
        except OSError:
            return None
    try:
        return max(0, int(raw))
    except ValueError:
        return None


def _read_clients_text():
    try:
        with open(PROC_CLIENTS, "r", encoding="utf-8", errors="replace") as f:
            return f.read()
    except OSError:
        return None


def parse_clients(text):
    """Parse /proc/asound/seq/clients into {client_id: (name, type, [ports])}."""
    clients = {}
    current = None
    for line in (text or "").splitlines():
        match = _CLIENT_RE.match(line)
        if match:
            client_id = int(match.group(1))
            current = client_id
            clients[client_id] = {
                "name": match.group(2).strip(),
                "type": match.group(3).strip(),
                "ports": [],
            }
            continue
        if current is None:
            continue
        port_match = _PORT_RE.match(line)
        if port_match:
            clients[current]["ports"].append({
                "port": int(port_match.group(1)),
                "name": port_match.group(2).strip(),
                "flags": port_match.group(3).strip(),
                "connecting_to": [],
            })
            continue
        # "    Connecting To: 128:0, 128:1" under the port it belongs to
        stripped = line.strip()
        if stripped.lower().startswith("connecting to:") and clients[current]["ports"]:
            targets = stripped.split(":", 1)[1]
            for chunk in targets.split(","):
                chunk = chunk.strip()
                if _ADDR_RE.match(chunk):
                    clients[current]["ports"][-1]["connecting_to"].append(chunk)
    return clients


def _is_controller(info):
    """A hardware MIDI source a player would actually hold."""
    name = info["name"].lower()
    if any(skip in name for skip in IGNORED_CLIENT_NAMES):
        return False
    if "fluid" in name:
        return False
    # User clients are software (fluidsynth, sequencers); controllers are Kernel.
    # Real hardware reports "Kernel,Card=1" rather than a bare "Kernel", so this
    # has to be a substring test - an exact match silently skipped every USB device.
    if "kernel" not in info["type"].lower():
        return False
    # Needs a readable port, i.e. something we can read events *from*.
    return any("R" in port["flags"] for port in info["ports"])


def input_ports(text=None):
    """Readable ports of every connected hardware controller, in client order.

    Order is stable for a given set of devices, so 'the second controller' means
    the same device across polls.
    """
    clients = parse_clients(text if text is not None else _read_clients_text())
    ports = []
    for client_id in sorted(clients):
        info = clients[client_id]
        if not _is_controller(info):
            continue
        for port in info["ports"]:
            if "R" in port["flags"]:
                ports.append(MidiPort(client_id, port["port"], info["name"],
                                      port["name"], port["flags"],
                                      port.get("connecting_to")))
                break   # one port per device is enough
    return ports


def fluid_ports(text=None):
    """fluidsynth's writable input ports, ordered by port number.

    With synth.midi-channels=32 there are two; port 1 feeds synth channels 16-31.
    """
    clients = parse_clients(text if text is not None else _read_clients_text())
    for client_id in sorted(clients):
        info = clients[client_id]
        if "fluid" not in info["name"].lower():
            continue
        found = [MidiPort(client_id, p["port"], info["name"], p["name"], p["flags"],
                          p.get("connecting_to"))
                 for p in sorted(info["ports"], key=lambda p: p["port"])
                 if "W" in p["flags"]]
        if found:
            return found
    return []


def device_count():
    """How many hardware MIDI controllers are connected."""
    faked = fake_device_count()
    if faked is not None:
        return faked
    return len(input_ports())


def _aconnect(args):
    try:
        result = subprocess.run(["aconnect"] + args, capture_output=True, text=True,
                                timeout=5)
    except (FileNotFoundError, OSError, subprocess.SubprocessError) as e:
        print(f"[MIDI] aconnect {' '.join(args)} unavailable: {type(e).__name__}")
        return False
    if result.returncode != 0:
        message = (result.stderr or result.stdout or "").strip()
        print(f"[MIDI] aconnect {' '.join(args)} failed: {message}")
        return False
    return True


_last_note = None


def _note(message):
    """Log only when the situation changes; this runs on every poll."""
    global _last_note
    if message != _last_note:
        _last_note = message
        print(f"[MIDI] {message}")


def ensure_devices_routed():
    """Pin each controller to exactly one fluidsynth input port.

    autoconnect attaches every controller to *every* input port fluidsynth
    exposes, so controller 1 ends up feeding port 1 as well and plays both voices
    at once. Each controller therefore needs its stray connections removed, not
    just the second one moved.

    Controller N gets port N; any beyond the number of ports fall back to port 0.
    Only connections to fluidsynth are touched - anything else a user has wired up
    is left alone.

    Re-asserted on every poll rather than done once: fluidsynth registers its ALSA
    ports a moment after launch, so a single attempt at boot can run before port 1
    exists, and autoconnect re-attaches devices when one is plugged in later.
    Verification is a /proc read, so aconnect only runs when the wiring is wrong.

    Returns True when every controller is correctly pinned, False if something
    could not be fixed, None when not applicable.
    """
    if fake_device_count() is not None:
        return None
    text = _read_clients_text()
    devices = input_ports(text)
    targets = fluid_ports(text)
    if not devices:
        return None
    if not targets:
        _note("fluidsynth has no input ports yet; waiting")
        return False
    if len(devices) >= 2 and len(targets) < 2:
        _note(f"fluidsynth exposes {len(targets)} input port(s); a second voice "
              "needs 2 (synth.midi-channels=32 with the alsa_seq driver)")
        return False

    fluid_addresses = {t.address for t in targets}
    ok = True
    for index, device in enumerate(devices):
        # Controller N gets port N; extras fall back to port 0, i.e. voice 1.
        port_index = index if index < len(targets) else 0
        wanted = targets[port_index].address
        voice = port_index + 1
        current = set(device.connecting_to)
        # Extra links to fluidsynth make this device play more than one voice.
        for stray in sorted((current & fluid_addresses) - {wanted}):
            _note(f"unlinking {device.client_name!r} ({device.address}) from "
                  f"{stray}; it should only feed {wanted}")
            if not _aconnect(["-d", device.address, stray]):
                ok = False
        if wanted not in current:
            _note(f"linking {device.client_name!r} ({device.address}) -> {wanted} "
                  f"(voice {voice})")
            if not _aconnect([device.address, wanted]):
                ok = False

    if ok:
        summary = ", ".join(
            f"{d.client_name}->{targets[i if i < len(targets) else 0].address}"
            for i, d in enumerate(devices))
        _note(f"routing settled: {summary}")
    return ok


def describe():
    """One-line summary for the boot log."""
    faked = fake_device_count()
    if faked is not None:
        return f"{faked} MIDI controller(s) [simulated]"
    ports = input_ports()
    if not ports:
        return "no MIDI controllers detected"
    names = ", ".join(f"{p.client_name} ({p.address})" for p in ports)
    return f"{len(ports)} MIDI controller(s): {names}"
