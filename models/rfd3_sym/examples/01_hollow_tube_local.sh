#!/usr/bin/env bash
# Example 1 — the canonical CLEAN HOLLOW TUBE, generated on a local GPU.
#
#   spt5_R20_L70_n10 : 5 subunits/turn, soft radius target 20 Å, 70-aa subunits,
#   10 chains. Emergent radius softly pinned to 20 Å; rise = subunit_height/5 so
#   turns stack into a continuous wall. This is the known-good "it works"
#   result (bonded, hollow, controllable lumen).
#
# Prereqs: the rfd3 environment (rc-foundry[rfd3] + torch) and a GPU with the
# RFD3 checkpoint at ~/.foundry/checkpoints/rfd3_latest.ckpt (or pass --ckpt-path).
# ~700 residues total -> runs on an RTX-class card with low_memory_mode.
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PKG="$(dirname "$HERE")"                 # models/rfd3_sym
OUT="${OUT:-$HERE/outputs}"
SEED="${SEED:-0}"

# rise = subunit_height(70)/5 = (0.25*70+8)/5 = 5.1 Å  (turn-stacking)
RISE=5.1

cd "$PKG"
PYTHONPATH="$PKG${PYTHONPATH:+:$PYTHONPATH}" \
python runners/run_local.py \
    --subunits-per-turn 5 --rise "$RISE" --n-subunits 10 \
    --subunit-length 70 --r-target 20 --seed "$SEED" \
    --tag spt5_R20_L70_n10 --out-dir "$OUT"

echo
echo "=== outputs (full paths) ==="
ls -1 "$OUT"/spt5_R20_L70_n10/*.cif.gz "$OUT"/spt5_R20_L70_n10/*provenance.json 2>/dev/null || true

# --- score it (needs the [validation] extra: gemmi + biotite) ---
CIF=$(ls "$OUT"/spt5_R20_L70_n10/*model_0.cif.gz 2>/dev/null | head -1 || true)
if [ -n "${CIF:-}" ]; then
    PDB="${CIF%.cif.gz}.pdb"
    python - "$CIF" "$PDB" <<'PY'
import sys, gzip, tempfile, gemmi
cif, out = sys.argv[1], sys.argv[2]
with tempfile.NamedTemporaryFile("w", suffix=".cif", delete=False) as t:
    t.write(gzip.open(cif, "rt").read()); tmp = t.name
st = gemmi.read_structure(tmp); st.setup_entities(); st.write_pdb(out)
print("wrote", out)
PY
    echo "=== scorecard (groove-complete AND all-aligned AND clash-free?) ==="
    python validation/scorecard.py "$PDB" 5 || true
    echo "PDB for viewing: $PDB"
fi
