import os
import json
from sf2utils.sf2parse import Sf2File
fi = '03_lozmm'
sf2_path = f"files/sf2/{fi}.sf2"
output_path = f"files/sf2_meta/{fi}.json"

# Ensure output directory exists
os.makedirs(os.path.dirname(output_path), exist_ok=True)

# --- Load SF2 ---
with open(sf2_path, "rb") as f:
    sf2 = Sf2File(f)

# --- Build preset map with tuple keys ---
preset_map = {}
for p in sf2.presets:
    # Skip placeholders
    if not p.name or p.name.upper() == "EOP":
        continue

    bank = getattr(p, "bank_id", getattr(p, "bank", 0))
    program = getattr(p, "preset_id", getattr(p, "preset", 0))

    preset_map[(bank, program)] = p.name

# --- Sort items by bank then program for consistent output ---
sorted_items = sorted(preset_map.items(), key=lambda kv: (kv[0][0], kv[0][1]))

# --- Save a JSON version (tuples converted to string keys for JSON) ---
json_preset_map = {f"{bank}:{program}": name for (bank, program), name in sorted_items}

with open(output_path, "w") as f:
    json.dump(json_preset_map, f, indent=2)

print(f"Saved preset map to {output_path} (tuple keys in Python, sorted by bank → program)")

# import json

# with open('files/sf2_meta/00_sm64.json', 'r') as f:
#     json_data = json.load(f)

# # Convert string keys back to tuple (bank, program)
# preset_map = {
#     tuple(map(int, key.split(":"))): name
#     for key, name in json_data.items()
# }

# print(preset_map[(0,0)])