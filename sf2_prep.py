# -------------------------
# SoundFont metadata extraction
# -------------------------
# Shared by scripts/sf_prepper.py (bulk CLI use on a dev machine) and by
# Synth.start() (auto-prep for any soundfont dropped in without metadata).
#
# sf2utils is only needed to *generate* metadata. Once the JSON exists it is read
# with the stdlib, so a device without sf2utils installed still runs normally --
# it just cannot prep a brand new soundfont on its own.
import os
import json
import logging

DRUM_BANK = 128


def _load_sf2(sf2_path):
    """Parse an SF2. Returns None if sf2utils isn't installed."""
    try:
        from sf2utils.sf2parse import Sf2File
    except ImportError:
        return None
    # sf2utils logs a warning per malformed sample loop; these soundfonts produce
    # hundreds and would bury the boot log.
    prior = logging.root.manager.disable
    logging.disable(logging.WARNING)
    try:
        with open(sf2_path, "rb") as f:
            return Sf2File(f)
    finally:
        logging.root.manager.disable = prior


def _bank_prog(preset):
    bank = getattr(preset, "bank_id", getattr(preset, "bank", 0))
    prog = getattr(preset, "preset_id", getattr(preset, "preset", 0))
    return bank, prog


def _usable_presets(sf2):
    for p in sf2.presets:
        if not p.name or p.name.upper() == "EOP":
            continue
        yield p


def _preset_name(preset):
    """SF2 name fields are space-padded to 20 bytes. Unstripped names render as
    over-wide strings and throw off the centred text blits on the 240px display.
    """
    return (preset.name or "").strip()


def build_meta_map(sf2_path, sf2=None):
    """{"bank:prog": preset_name} for every playable preset, sorted by bank then prog.

    Matches the output format of the original prepper script so regenerating an
    existing soundfont's metadata is a no-op.
    """
    sf2 = sf2 or _load_sf2(sf2_path)
    if sf2 is None:
        return None
    preset_map = {}
    for p in _usable_presets(sf2):
        preset_map[_bank_prog(p)] = _preset_name(p)
    return {
        f"{bank}:{prog}": name
        for (bank, prog), name in sorted(preset_map.items(), key=lambda kv: kv[0])
    }


def build_drum_map(sf2_path, sf2=None):
    """{"128:prog": {"name": ..., "notes": [...]}} for every bank-128 drum kit.

    Per-note *names* are not recoverable -- SF2 sample names in these files are
    placeholders like "Sample 17-4" -- but the populated key ranges are, and those
    are what matter: they tell the binding editor which notes actually sound.
    Labels come from the GM percussion map instead.
    """
    sf2 = sf2 or _load_sf2(sf2_path)
    if sf2 is None:
        return None
    kits = {}
    for p in _usable_presets(sf2):
        bank, prog = _bank_prog(p)
        if bank != DRUM_BANK:
            continue
        notes = set()
        for pbag in p.bags:
            inst = getattr(pbag, "instrument", None)
            if inst is None:
                continue
            for ibag in inst.bags:
                key_range = getattr(ibag, "key_range", None)
                if key_range is None:
                    continue  # global zone, carries no key mapping
                lo, hi = key_range[0], key_range[1]
                if lo is None or hi is None or hi < lo:
                    continue
                notes.update(range(lo, hi + 1))
        if not notes:
            continue
        kits[f"{bank}:{prog}"] = {"name": _preset_name(p), "notes": sorted(notes)}
    return kits


def _write_json(path, obj):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(obj, f, indent=2)
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp, path)


def ensure_metadata(sf2_paths, meta_folder, drum_folder, force=False):
    """Generate any missing sf2_meta / sf2_drums JSON for the given soundfonts.

    Returns (generated, skipped) lists of soundfont basenames. Only parses a
    soundfont when something is actually missing, so the normal boot cost is zero.
    An empty drum map is still written, so a soundfont with no kits isn't reparsed
    on every boot.
    """
    generated, skipped = [], []
    for sf2_path in sf2_paths:
        name = os.path.splitext(os.path.basename(sf2_path))[0]
        meta_path = os.path.join(meta_folder, name + ".json")
        drum_path = os.path.join(drum_folder, name + ".json")
        need_meta = force or not os.path.exists(meta_path)
        need_drums = force or not os.path.exists(drum_path)
        if not (need_meta or need_drums):
            continue

        print(f"[SF2 PREP] {name}: parsing (meta={need_meta} drums={need_drums})")
        sf2 = _load_sf2(sf2_path)
        if sf2 is None:
            print("[SF2 PREP] sf2utils not installed - cannot prep new soundfonts. "
                  f"Skipping {name}; generate its metadata on a dev machine with "
                  "scripts/sf_prepper.py")
            skipped.append(name)
            continue

        try:
            if need_meta:
                meta = build_meta_map(sf2_path, sf2)
                _write_json(meta_path, meta)
                print(f"[SF2 PREP] {name}: wrote {len(meta)} presets")
            if need_drums:
                drums = build_drum_map(sf2_path, sf2)
                _write_json(drum_path, drums)
                print(f"[SF2 PREP] {name}: wrote {len(drums)} drum kits")
            generated.append(name)
        except Exception as e:
            # A malformed soundfont must not stop the device from booting.
            print(f"[SF2 PREP] FAILED on {name}: {type(e).__name__}: {e}")
            skipped.append(name)
    return generated, skipped
