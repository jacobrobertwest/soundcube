from settings import *
import sf2_prep

class Synth:
    def __init__(self, soundcube_runmode):
        self.runmode = soundcube_runmode
        self.fs_terminal = None
        self.fs_alive = False
        self.drum_mode = False
        self.drum_kits = []
        self.selected_kit_index = 0
        self.drum_velocity = DRUM_VELOCITY_DEFAULT
        self.pad_notes = deepcopy(DEFAULT_PAD_NOTES)

    def start(self):
        print("Synth starting...")
        self.sf_folder = 'files/sf2'
        self.icon_folder = 'files/sf2_icon'
        self.meta_folder = 'files/sf2_meta'
        self.drum_meta_folder = 'files/sf2_drums'
        self.fx_icon_folder = 'files/fx_icon'
        self.presets_file = 'files/presets.json'
        self.kits_file = 'files/kits.json'

        # Soundfont load order defines fluidsynth's 1-based sfont ids, so this
        # list is the index of record for everything keyed off active_sf2.
        self.sf2_files = sorted(glob.glob(os.path.join(self.sf_folder, "*.sf2")))
        self.sf2_names = [os.path.splitext(os.path.basename(p))[0] for p in self.sf2_files]

        # Generate sidecars for any soundfont dropped in without them. Only parses
        # when something is actually missing, so a normal boot costs nothing.
        sf2_prep.ensure_metadata(self.sf2_files, self.meta_folder, self.drum_meta_folder)

        self.load_meta_maps()
        self.load_bank_icons()
        self.load_drum_kits()

        self.presets = self._load_json_with_fallback(
            self.presets_file, self._default_presets())
        self.num_presets = len(self.presets)
        self.on_last_preset = False
        self.presets_maxed_out = self.num_presets == 99

        self.fx_dict = FX_LIBRARY
        self.effects = list(self.fx_dict.keys())
        self.fx_icon_files = sorted(
            f for f in os.listdir(self.fx_icon_folder)
            if f.endswith(".png")
        )
        self.fx_icons = [pygame.image.load(os.path.join(self.fx_icon_folder, f)).convert_alpha() for f in self.fx_icon_files]
        self.selected_effect_index = 0
        self.selected_fx_icon = self.fx_icons[self.selected_effect_index]
        self.selected_fx_meta_map = self.fx_dict[self.effects[self.selected_effect_index]]

        self.load_kits()

        if self.runmode == 'prod' or self.wants_audio():
            self.run_synth()
        return True

    # Platform audio driver. Dev machines are macs, the device is a Pi.
    AUDIO_DRIVERS = {"darwin": "coreaudio"}

    def wants_audio(self):
        """Dev mode starts fluidsynth too when it's installed, so pad bindings and
        velocity can be worked on without the Pi in the loop.

        Set SOUNDCUBE_AUDIO=0 to fall back to printing commands instead. Ignored in
        prod, which always needs real audio.
        """
        return os.getenv("SOUNDCUBE_AUDIO", "1") != "0"

    def run_synth(self):
        # Build the command
        cmd = [
            "fluidsynth",
            "-a", self.AUDIO_DRIVERS.get(sys.platform, "alsa"),
            "-o", "midi.autoconnect=True",
            "-o", "synth.cpu-cores=4"
        ]
        cmd.append(self.sf2_files[0])
        cmd.append("files/bootup.mid")

        # start the subprocess terminal
        try:
            self.fs_terminal = subprocess.Popen(
                cmd,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )
        except (FileNotFoundError, OSError) as e:
            # No fluidsynth on this machine. send_command falls back to printing,
            # which is a usable dev mode rather than a crash.
            print(f"[FS ERROR] could not start fluidsynth ({type(e).__name__}: {e})")
            print("[FS ERROR] continuing with commands printed to stdout only")
            self.fs_terminal = None
            self.fs_alive = False
            return False
        self.fs_alive = True

        def watch_output():
            for line in self.fs_terminal.stdout:
                print("[FLUIDSYNTH]", line.strip())

        def watch_errors():
            for line in self.fs_terminal.stderr:
                print("[FS ERROR]", line.strip())

        threading.Thread(target=watch_output, daemon=True).start()
        threading.Thread(target=watch_errors, daemon=True).start()
        return True

    # post boot up
    def post_boot_init(self):
        for f in self.sf2_files[1:]:
            self.send_command(f"load {f}")
        self.send_command("fonts")
        self.send_command(f"set synth.polyphony {BASE_POLYPHONY}")
        self.send_command("router_clear")
        self.send_command("router_begin cc")
        self.send_command("router_end")
        self.send_command("router_begin note")
        self.send_command("router_end")
        self.send_command("router_begin prog")
        self.send_command("router_end")
        self.send_command("router_begin pbend")
        self.send_command("router_par1 0 20000 0.5 4096")
        self.send_command("router_end")
        self.send_command("router_begin cpress")
        self.send_command("router_end")
        self.send_command("router_begin kpress")
        self.send_command("router_end")
        self.handle_preset_change(1)

    # send command to subprocess terminal running fluidsynth
    def send_command(self, command):
        if not self.fs_terminal:
            print(f'[FLUIDSYNTH] {command}')
            return
        if SOUNDCUBE_DEBUG:
            print(f'[CMD] {command}')
        try:
            self.fs_terminal.stdin.write(command + "\n")
            self.fs_terminal.stdin.flush()
        except (BrokenPipeError, OSError, ValueError) as e:
            # fluidsynth has gone away. A dead synth must not become a dead
            # appliance, so note it and keep the UI running.
            if self.fs_alive:
                print(f"[FS ERROR] lost fluidsynth ({type(e).__name__}: {e})")
                self.fs_alive = False

    # -------------------------
    # Durable JSON
    # -------------------------
    def _atomic_write_json(self, path, obj):
        """Write via temp file + fsync + rename.

        A plain truncate-then-write loses the whole file if power drops mid-write,
        and both presets.json and kits.json are gitignored, so there is no way to
        restore one in the field.
        """
        tmp = path + ".tmp"
        try:
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(obj, f, indent=2, separators=(",", ": "))
                f.flush()
                os.fsync(f.fileno())
            os.replace(tmp, path)
        except OSError as e:
            print(f"[ERROR] could not write {path}: {e}")
            return False
        try:
            shutil.copyfile(path, path + ".bak")
        except OSError as e:
            print(f"[WARN] could not refresh backup for {path}: {e}")
        return True

    def _load_json_with_fallback(self, path, default):
        """Try the file, then its .bak, then a built-in default.

        Never raises: a corrupt data file must not stop the device from booting.
        """
        backup = path + ".bak"
        if not os.path.exists(path) and not os.path.exists(backup):
            return deepcopy(default)
        for candidate in (path, backup):
            if not os.path.exists(candidate):
                continue
            try:
                with open(candidate, "r", encoding="utf-8") as f:
                    data = json.load(f)
                if candidate != path:
                    print(f"[RECOVERY] {path} was unreadable; loaded {candidate}")
                return data
            except (OSError, json.JSONDecodeError, UnicodeDecodeError) as e:
                print(f"[WARN] could not load {candidate}: {type(e).__name__}: {e}")
        print(f"[RECOVERY] falling back to built-in defaults for {path}")
        return deepcopy(default)

    def _default_presets(self):
        """One valid preset, built from whichever soundfont has usable metadata."""
        sf2_index, bank, inst = 1, 0, 0
        for i, meta in enumerate(self.meta_maps, start=1):
            if meta:
                sf2_index = i
                bank, inst = sorted(meta.keys())[0]
                break
        fx = {name: {"value": cfg["def"], "params": None}
              for name, cfg in FX_LIBRARY.items()}
        return {
            "1": {
                "sf2": sf2_index, "bank": bank, "inst": inst,
                "breathmode": False, "poly_mode": True, "fx": fx,
            }
        }

    # -------------------------
    # Soundfont sidecars
    # -------------------------
    def load_meta_maps(self):
        """One preset-name map per soundfont, aligned to sf2_files by filename.

        Pairing by sorted position across separate directories meant that adding a
        soundfont shifted every saved preset's sf2 index onto a different
        instrument. Keying by name makes the alignment correct by construction.
        """
        self.meta_maps = []
        for name in self.sf2_names:
            path = os.path.join(self.meta_folder, name + ".json")
            preset_map = {}
            try:
                with open(path, "r", encoding="utf-8") as f:
                    raw_map = json.load(f)
                preset_map = {
                    tuple(map(int, key.split(":"))): value
                    for key, value in raw_map.items()
                }
            except (OSError, json.JSONDecodeError, ValueError) as e:
                print(f"[WARN] no usable metadata for {name}: {type(e).__name__}: {e}")
            self.meta_maps.append(preset_map)

    def load_bank_icons(self):
        """One icon per soundfont, aligned by filename, placeholder when absent."""
        self.bank_icons = []
        for name in self.sf2_names:
            path = os.path.join(self.icon_folder, name + ".png")
            try:
                self.bank_icons.append(pygame.image.load(path).convert_alpha())
            except (pygame.error, OSError):
                print(f"[WARN] no icon for {name}, using placeholder")
                self.bank_icons.append(self._placeholder_icon())

    def _placeholder_icon(self):
        icon = pygame.Surface((50, 50), pygame.SRCALPHA)
        pygame.draw.rect(icon, (90, 90, 90), icon.get_rect(), width=2, border_radius=6)
        glyph = SECONDARY_FONT.render("?", True, (150, 150, 150))
        icon.blit(glyph, glyph.get_rect(center=(25, 25)))
        return icon

    def load_drum_kits(self):
        """Flat list of every bank-128 kit across all soundfonts.

        Built from the drum sidecars rather than from sf2_files, because most
        soundfonts contain no kits at all and would be dead entries to scroll past.
        """
        self.drum_kits = []
        for sf2_index, name in enumerate(self.sf2_names, start=1):
            path = os.path.join(self.drum_meta_folder, name + ".json")
            try:
                with open(path, "r", encoding="utf-8") as f:
                    raw = json.load(f)
            except (OSError, json.JSONDecodeError) as e:
                print(f"[WARN] no drum metadata for {name}: {type(e).__name__}")
                continue
            for key in sorted(raw, key=lambda k: self._prog_of(k)):
                try:
                    bank, prog = map(int, key.split(":"))
                except (ValueError, AttributeError):
                    continue
                if bank != DRUM_BANK:
                    continue
                try:
                    notes = sorted({int(n) for n in raw[key].get("notes", [])})
                except (TypeError, ValueError):
                    continue
                if not notes:
                    continue
                self.drum_kits.append({
                    "sf2": sf2_index,
                    "prog": prog,
                    "name": raw[key].get("name") or f"KIT {prog}",
                    "notes": notes,
                    "noteset": frozenset(notes),
                })
        print(f"[DRUMS] {len(self.drum_kits)} drum kits found")

    @staticmethod
    def _prog_of(key):
        try:
            return int(key.split(":")[1])
        except (ValueError, IndexError, AttributeError):
            return 0

    # -------------------------
    # Drum kit bindings (kits.json)
    # -------------------------
    def load_kits(self):
        default = {
            "version": 1,
            "selected_kit": 0,
            "velocity": DRUM_VELOCITY_DEFAULT,
            "pads": deepcopy(DEFAULT_PAD_NOTES),
        }
        data = self._load_json_with_fallback(self.kits_file, default)
        if not isinstance(data, dict):
            data = default

        raw_pads = data.get("pads")
        if not isinstance(raw_pads, dict):
            raw_pads = {}
        self.pad_notes = {}
        for pad, fallback in DEFAULT_PAD_NOTES.items():
            try:
                note = int(raw_pads.get(pad, fallback))
            except (TypeError, ValueError):
                note = fallback
            self.pad_notes[pad] = max(0, min(127, note))

        try:
            velocity = int(data.get("velocity", DRUM_VELOCITY_DEFAULT))
        except (TypeError, ValueError):
            velocity = DRUM_VELOCITY_DEFAULT
        self.drum_velocity = max(DRUM_VELOCITY_MIN, min(DRUM_VELOCITY_MAX, velocity))

        try:
            index = int(data.get("selected_kit", 0))
        except (TypeError, ValueError):
            index = 0
        self.selected_kit_index = index % len(self.drum_kits) if self.drum_kits else 0

    def save_kits(self):
        ok = self._atomic_write_json(self.kits_file, {
            "version": 1,
            "selected_kit": self.selected_kit_index,
            "velocity": self.drum_velocity,
            "pads": dict(self.pad_notes),
        })
        print("Saved drum kit" if ok else "Failed to save drum kit")
        return ok

    # -------------------------
    # Drum performance mode
    # -------------------------
    def has_drum_kits(self):
        return bool(self.drum_kits)

    def active_drum_kit(self):
        if not self.drum_kits:
            return None
        return self.drum_kits[self.selected_kit_index]

    def enter_drum_mode(self):
        self.drum_mode = True
        # Stop the boot jingle. It plays notes and program changes on channels
        # 0,1,2,3,7,8,9 - including the drum channel - and in dev mode (2s boot) it
        # is still running when drum mode starts.
        self.send_command("player_stop")
        # The drum channel needs its own basic channel or noteon on it is silently
        # dropped: setbasicchannels 0 2 1 leaves every other channel disabled.
        # Deliberately no resetbasicchannels here, so channel 0 keeps whatever the
        # melodic preset configured and the MIDI controller keeps working.
        self.send_command(f"setbasicchannels {DRUM_CHANNEL} 2 1")
        # Mono would make each hit steal the previous note; breath mode would gate
        # volume by CC2 and produce silence with no breath controller attached.
        self.send_command(f"setbreathmode {DRUM_CHANNEL} 0 0 0")
        self.send_command(f"set synth.polyphony {DRUM_POLYPHONY}")
        self.select_drum_kit(self.selected_kit_index)

    def exit_drum_mode(self):
        self.drum_mode = False
        self.panic_kill(DRUM_CHANNEL)
        self.panic_kill()
        self.send_command(f"set synth.polyphony {BASE_POLYPHONY}")
        # replays poly/mono, breath mode, fx chain and the melodic patch, and its
        # resetbasicchannels releases the drum channel again
        self.handle_preset_change(self.loaded_preset_num)

    def select_drum_kit(self, index):
        if not self.drum_kits:
            return None
        self.selected_kit_index = index % len(self.drum_kits)
        kit = self.active_drum_kit()
        self.send_command(
            f"select {DRUM_CHANNEL} {kit['sf2']} {DRUM_BANK} {kit['prog']}")
        return kit

    def cycle_drum_kit(self, delta):
        return self.select_drum_kit(self.selected_kit_index + delta)

    def drum_kit_icon(self):
        kit = self.active_drum_kit()
        if kit is None:
            return None
        index = kit["sf2"] - 1
        if 0 <= index < len(self.bank_icons):
            return self.bank_icons[index]
        return None

    def resolve_drum_note(self, note):
        """Nearest note that actually sounds in the current kit.

        poke kits populate only 36 of the 47 GM notes, so a stored binding can
        point at a silent note. Bindings are kept verbatim and resolved here
        instead, so they survive kit changes and no pad is ever dead.
        """
        kit = self.active_drum_kit()
        if kit is None or note in kit["noteset"]:
            return note
        return min(kit["notes"], key=lambda n: (abs(n - note), n))

    def pad_note(self, pad_name):
        return self.pad_notes.get(pad_name, DEFAULT_PAD_NOTES.get(pad_name, 36))

    def set_pad_note(self, pad_name, note):
        self.pad_notes[pad_name] = max(0, min(127, int(note)))

    def adjust_velocity(self, delta):
        self.drum_velocity = max(
            DRUM_VELOCITY_MIN,
            min(DRUM_VELOCITY_MAX, self.drum_velocity + delta))
        return self.drum_velocity

    def drum_noteon(self, note, velocity=None):
        vel = self.drum_velocity if velocity is None else velocity
        self.send_command(f"noteon {DRUM_CHANNEL} {note} {vel}")

    def drum_noteoff(self, note):
        self.send_command(f"noteoff {DRUM_CHANNEL} {note}")

    # --- PERFORMANCE / SELECT MODE -----
    def _normalize_fx(self, raw):
        """An fx chain holding exactly the FX_LIBRARY effects, with usable values.

        presets.json is gitignored, hand-editable, and can come back from a .bak
        recovery, so a preset's fx block may be missing an effect, carry a stale key
        from an older format, or hold a non-numeric value. handle_preset_change only
        filled in a *wholly absent* block, so any of those reached render() as a
        KeyError or TypeError and took the whole appliance down.

        The effect list is fixed (these three are what fluidsynth exposes natively),
        so this is a straight repair to that shape - unknown keys are dropped and
        values are coerced into range.
        """
        if not isinstance(raw, dict):
            raw = {}
        chain = {}
        for effect, cfg in self.fx_dict.items():
            default = cfg['def']
            entry = raw.get(effect)
            entry = entry if isinstance(entry, dict) else {}
            try:
                value = float(entry.get('value'))
            except (TypeError, ValueError):
                value = float(default)
            if value != value or value in (float('inf'), float('-inf')):
                value = float(default)
            low, high = cfg['rng'][0], cfg['rng'][1]
            value = max(low, min(high, value))
            # Keep on/off switches as ints so they round-trip through JSON unchanged.
            value = int(round(value)) if isinstance(default, int) else round(value, 3)
            chain[effect] = {'value': value, 'params': entry.get('params')}
        return chain

    def handle_preset_change(self, index):
        self.loaded_preset_num = index
        self.loaded_preset = deepcopy(self.presets[str(self.loaded_preset_num)])
        self.active_sf2 = self.loaded_preset["sf2"]
        self.active_bank = self.loaded_preset["bank"]
        self.active_inst = self.loaded_preset["inst"]
        self.active_breathmode = self.loaded_preset["breathmode"]
        self.active_poly_mode = self.loaded_preset["poly_mode"]
        # Normalise rather than only filling in a wholly absent 'fx' block: a
        # partial or hand-edited one used to raise inside render().
        self.active_fx_chain = self._normalize_fx(self.loaded_preset.get('fx'))
        self.loaded_preset['fx'] = deepcopy(self.active_fx_chain)
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
        self.on_last_preset = self.loaded_preset_num == self.num_presets

    def enforce_fx(self):
        for effect in self.active_fx_chain:
            self.send_command(self.fx_dict[effect]['cmd'].format(val=self.active_fx_chain[effect]['value']))
            # if self.active_fx_chain[effect]['params'] is not None:
            #     for param in self.active_fx_chain[effect]['params']:
            #         self.send_command(self.fx_dict[effect]['params'][param]['cmd'].format(val=self.active_fx_chain[effect]['params'][param]))

    def enforce_active_elements(self):
        self.active_sf2_meta = self.meta_maps[self.active_sf2 - 1]
        self.active_preset_name = self.active_sf2_meta.get(
            (self.active_bank, self.active_inst),
            f"{self.active_bank}:{self.active_inst}")
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

    def extend_preset(self):
        if self.num_presets < 99:
            self.loaded_preset_num += 1
            self.presets[str(self.loaded_preset_num)] = {}
            self.presets[str(self.loaded_preset_num)]['sf2'] = self.active_sf2
            self.presets[str(self.loaded_preset_num)]['bank'] = self.active_bank
            self.presets[str(self.loaded_preset_num)]['inst'] = self.active_inst
            self.presets[str(self.loaded_preset_num)]['breathmode'] = self.active_breathmode
            self.presets[str(self.loaded_preset_num)]['poly_mode'] = self.active_poly_mode
            self.presets[str(self.loaded_preset_num)]['fx'] = deepcopy(self.active_fx_chain)
            self._atomic_write_json(self.presets_file, self.presets)
            self.num_presets = len(self.presets)
            self.presets_maxed_out = self.num_presets == 99

    def panic_kill(self, channel=0):
        # control change | channel | cc123 (kill all notes) | value (not used for this CC, but required)
        self.send_command(f"cc {channel} 121 0")
        self.send_command(f"cc {channel} 123 0")

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
        """Advance to the next soundfont that has usable metadata.

        A soundfont can have an empty meta map when it was added on a device
        without sf2utils available to prep it; scrolling onto one would otherwise
        raise on keys[0].
        """
        total = len(self.sf2_files)
        for step in range(1, total + 1):
            candidate = ((self.active_sf2 - 1 + step) % total) + 1
            if self.meta_maps[candidate - 1]:
                break
        else:
            return
        self.active_sf2 = candidate
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
        self._atomic_write_json(self.presets_file, self.presets)
        print('Saved preset')

    def exit_settings_mode(self):
        print('Exiting settings mode')
        self.selected_effect_index = 0
        self.selected_fx_icon = self.fx_icons[self.selected_effect_index]
        self.selected_fx_meta_map = self.fx_dict[self.effects[self.selected_effect_index]]
        self.handle_preset_change(self.loaded_preset_num)

    def stop(self):
        print("Synth stopping...")
        self.fs_alive = False
        if self.fs_terminal:
            self.fs_terminal.terminate()
            try:
                self.fs_terminal.wait(timeout=2)
            except subprocess.TimeoutExpired:
                print("[FS] did not exit in time, killing")
                self.fs_terminal.kill()
