import json
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
JSON_FILE = BASE_DIR / "output" / "gex_levels.json"
PINE_FILE = BASE_DIR / "output" / "NQ_GEX_ENGINE_V4.pine"


def load_gex():
    with open(JSON_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def generate_pine(data):
    full = data["full_chain"]

    gamma_flip = full["gamma_flip_nq"]
    call_wall = full["call_wall_nq"]
    put_wall = full["put_wall_nq"]
    max_pain = full["max_pain_nq"]

    pine = f'''//@version=6
indicator("NQ GEX ENGINE V4", overlay=true, max_lines_count=100, max_labels_count=100)

// ============================================================
// AUTOMATICALLY GENERATED FROM PYTHON GEX ENGINE
// Do not manually edit the level values.
// ============================================================

gammaFlip = {gamma_flip}
callWall  = {call_wall}
putWall   = {put_wall}
maxPain   = {max_pain}

// ============================================================
// GEX LEVELS
// ============================================================

plot(
     gammaFlip,
     title="Gamma Flip",
     color=color.purple,
     linewidth=2,
     style=plot.style_stepline
)

plot(
     callWall,
     title="Call Wall",
     color=color.red,
     linewidth=2,
     style=plot.style_stepline
)

plot(
     putWall,
     title="Put Wall",
     color=color.green,
     linewidth=2,
     style=plot.style_stepline
)

plot(
     maxPain,
     title="Max Pain",
     color=color.gray,
     linewidth=1,
     style=plot.style_stepline
)

// ============================================================
// LABELS
// ============================================================

var label gammaLabel = na
var label callLabel  = na
var label putLabel   = na
var label painLabel  = na

if barstate.islast

    if not na(gammaLabel)
        label.delete(gammaLabel)

    if not na(callLabel)
        label.delete(callLabel)

    if not na(putLabel)
        label.delete(putLabel)

    if not na(painLabel)
        label.delete(painLabel)

    gammaLabel := label.new(
         bar_index,
         gammaFlip,
         "GAMMA FLIP  " + str.tostring(gammaFlip, "#.##"),
         style=label.style_label_left,
         textcolor=color.white,
         color=color.purple
     )

    callLabel := label.new(
         bar_index,
         callWall,
         "CALL WALL  " + str.tostring(callWall, "#.##"),
         style=label.style_label_left,
         textcolor=color.white,
         color=color.red
     )

    putLabel := label.new(
         bar_index,
         putWall,
         "PUT WALL  " + str.tostring(putWall, "#.##"),
         style=label.style_label_left,
         textcolor=color.white,
         color=color.green
     )

    painLabel := label.new(
         bar_index,
         maxPain,
         "MAX PAIN  " + str.tostring(maxPain, "#.##"),
         style=label.style_label_left,
         textcolor=color.white,
         color=color.gray
     )
''' 

    with open(PINE_FILE, "w", encoding="utf-8") as f:
        f.write(pine)

    print()
    print("=" * 60)
    print("PINE SCRIPT UPDATED")
    print("=" * 60)
    print()
    print(f"Gamma Flip : {gamma_flip}")
    print(f"Call Wall  : {call_wall}")
    print(f"Put Wall   : {put_wall}")
    print(f"Max Pain   : {max_pain}")
    print()
    print("Saved to:")
    print(PINE_FILE)
    print()


if __name__ == "__main__":
    data = load_gex()
    generate_pine(data)
