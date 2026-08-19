# -------------------------
# SoundFont metadata prepper (CLI)
# -------------------------
# Bulk-generates the JSON sidecars for the soundfonts in files/sf2/.
# The device also does this automatically at boot for any soundfont missing
# metadata (see Synth.start), so this script is mainly for regenerating in bulk
# or prepping on a dev machine before committing.
#
#   python3 scripts/sf_prepper.py                  # fill in whatever is missing
#   python3 scripts/sf_prepper.py --drums          # drum maps only
#   python3 scripts/sf_prepper.py --force          # regenerate everything
#   python3 scripts/sf_prepper.py --only 09_kkslider
#
# Requires sf2utils:  pip install sf2utils
import argparse
import glob
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
import sf2_prep

SF2_FOLDER = "files/sf2"
META_FOLDER = "files/sf2_meta"
DRUM_FOLDER = "files/sf2_drums"


def main():
    ap = argparse.ArgumentParser(description="Generate SF2 metadata sidecars.")
    ap.add_argument("--meta", action="store_true", help="only preset name maps")
    ap.add_argument("--drums", action="store_true", help="only drum kit note maps")
    ap.add_argument("--force", action="store_true", help="regenerate even if present")
    ap.add_argument("--only", metavar="NAME", help="a single soundfont, without .sf2")
    args = ap.parse_args()

    # Neither flag given means both.
    do_meta = args.meta or not args.drums
    do_drums = args.drums or not args.meta

    paths = sorted(glob.glob(os.path.join(SF2_FOLDER, "*.sf2")))
    if args.only:
        paths = [p for p in paths
                 if os.path.splitext(os.path.basename(p))[0] == args.only]
        if not paths:
            sys.exit(f"No soundfont named {args.only!r} in {SF2_FOLDER}")

    if not paths:
        sys.exit(f"No .sf2 files found in {SF2_FOLDER}")

    if sf2_prep._load_sf2(paths[0]) is None:
        sys.exit("sf2utils is not installed.  pip install sf2utils")

    for path in paths:
        name = os.path.splitext(os.path.basename(path))[0]
        meta_path = os.path.join(META_FOLDER, name + ".json")
        drum_path = os.path.join(DRUM_FOLDER, name + ".json")

        wants = []
        if do_meta and (args.force or not os.path.exists(meta_path)):
            wants.append("meta")
        if do_drums and (args.force or not os.path.exists(drum_path)):
            wants.append("drums")
        if not wants:
            print(f"{name}: up to date")
            continue

        sf2 = sf2_prep._load_sf2(path)
        if "meta" in wants:
            meta = sf2_prep.build_meta_map(path, sf2)
            sf2_prep._write_json(meta_path, meta)
            print(f"{name}: {len(meta)} presets -> {meta_path}")
        if "drums" in wants:
            drums = sf2_prep.build_drum_map(path, sf2)
            sf2_prep._write_json(drum_path, drums)
            kits = ", ".join(f"{v['name']}({len(v['notes'])}n)"
                             for v in drums.values()) or "none"
            print(f"{name}: {len(drums)} drum kits -> {drum_path}  [{kits}]")


if __name__ == "__main__":
    main()
