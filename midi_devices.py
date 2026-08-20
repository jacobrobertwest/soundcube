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


def ensure_second_device_routed():
    """Keep controller 2 feeding fluidsynth's port 1, re-checking on every poll.

    Deliberately re-asserted rather than done once. fluidsynth registers its ALSA
    ports a moment after launch, so the first attempt at boot can easily run before
    port 1 exists; a single shot would then leave both controllers on port 0
    forever, which is exactly one voice playing twice. autoconnect can also
    re-attach a device to port 0 later.

    Verification is a /proc read, so aconnect only runs when something is wrong.
    Returns True when routed, False when it could not be, None when not applicable.
    """
    if fake_device_count() is not None:
        return None
    text = _read_clients_text()
    devices = input_ports(text)
    if len(devices) < 2:
        return None
    targets = fluid_ports(text)
    if len(targets) < 2:
        _note(f"fluidsynth exposes {len(targets)} input port(s); waiting for a "
              "second one (needs synth.midi-channels=32 and the alsa_seq driver)")
        return False

    device, port0, port1 = devices[1], targets[0], targets[1]
    if device.connecting_to == [port1.address]:
        _note(f"controller 2 {device.client_name!r} -> {port1.address} (voice 2)")
        return True

    _note(f"routing controller 2 {device.client_name!r} ({device.address}) "
          f"from {device.connecting_to or 'nothing'} to {port1.address}")
    if port0.address in device.connecting_to:
        _aconnect(["-d", device.address, port0.address])
    if not _aconnect([device.address, port1.address]):
        _note(f"could not route {device.client_name!r}; it stays on voice 1")
        return False
    return True


def route_second_device():
    """Put the second controller on fluidsynth's port 1 (synth channels 16-31).

    autoconnect has already wired every device to port 0, so the second one is
    disconnected from port 0 first. Returns the MidiPort that was moved, or None.

    Failing here is not fatal: the device simply stays on port 0 and plays voice 1,
    which is exactly the current single-voice behaviour.
    """
    if fake_device_count() is not None:
        return None
    devices = input_ports()
    targets = fluid_ports()
    if len(devices) < 2:
        return None
    if len(targets) < 2:
        print(f"[MIDI] fluidsynth exposes {len(targets)} input port(s); "
              "need 2 for a second voice (is synth.midi-channels=32 set?)")
        return None
    device, port0, port1 = devices[1], targets[0], targets[1]
    print(f"[MIDI] routing {device.client_name!r} ({device.address}) "
          f"to fluidsynth port {port1.address} for voice 2")
    _aconnect(["-d", device.address, port0.address])
    if not _aconnect([device.address, port1.address]):
        print("[MIDI] second voice routing failed; that device stays on voice 1")
        return None
    return device


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
