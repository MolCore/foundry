#!/usr/bin/env bash
# Example 2 — HALF-INTEGER STAGGERED GROOVE, close-packed, on Modal (L40S).
#
#   spt6.5, n=16 : 6.5 subunits/turn is a 2-start helix — each subunit nestles
#   into the groove between its two turn neighbours (offsets {1,6,7}). With
#   subunit_size 26 Å the close-pack solve gives R≈28.75 Å, rise≈3.31 Å, so the
#   whole groove shell of a central subunit is in contact. 16 chains > the
#   ceil(2t)+2 = 15 needed for one fully-coordinated central subunit.
#
# Prereqs: `modal` configured for the MolCore workspace. Runs on the
# `foundry-rfd3-tube` app; results land on the `sym-rfd3-tube-results` volume
# AND are pulled back locally below. (Modal caps workers at 6 in the app.)
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PKG="$(dirname "$HERE")"                 # models/rfd3_sym
OUT="${OUT:-$HERE/outputs}"
SEED="${SEED:-0}"

TAG=spt6p5_R29_L70_n16          # R rounds to 29 in the runner's tag
VOL=sym-rfd3-tube-results

cd "$PKG/runners"
# close-pack geometry is derived in-runner via --rise-override; we pass the
# analytic R (29) and rise (3.31) from closepack.close_packed_geometry(6.5, 26).
modal run run_modal.py::run \
    --subunits-per-turn 6.5 --n-subunits 16 \
    --subunit-length 70 --r-target 29 --rise-override 3.31 --seed "$SEED"

echo
echo "=== pull results from the Modal volume ==="
DST="$OUT/$TAG/seed_$(printf '%04d' "$SEED")"
mkdir -p "$DST"
for f in $(modal volume ls "$VOL" "$TAG/seed_$(printf '%04d' "$SEED")" 2>/dev/null \
            | grep -oE '[^ /]+\.(cif\.gz|json)$'); do
    modal volume get --force "$VOL" "$TAG/seed_$(printf '%04d' "$SEED")/$f" "$DST/" >/dev/null 2>&1 || true
done
echo "=== outputs (full paths) ==="
ls -1 "$DST"/*.cif.gz "$DST"/*provenance.json 2>/dev/null || echo "(nothing pulled — check 'modal volume ls $VOL')"

CIF=$(ls "$DST"/*model_0.cif.gz 2>/dev/null | head -1 || true)
if [ -n "${CIF:-}" ]; then
    PDB="${CIF%.cif.gz}.pdb"
    cd "$PKG"
    python - "$CIF" "$PDB" <<'PY'
import sys, gzip, tempfile, gemmi
cif, out = sys.argv[1], sys.argv[2]
with tempfile.NamedTemporaryFile("w", suffix=".cif", delete=False) as t:
    t.write(gzip.open(cif, "rt").read()); tmp = t.name
st = gemmi.read_structure(tmp); st.setup_entities(); st.write_pdb(out)
print("wrote", out)
PY
    echo "=== scorecard (offsets {1,6,7} for t=6.5) ==="
    python validation/scorecard.py "$PDB" 6.5 || true
    echo "=== coordination-shell BSA by offset (the polymerisation interface) ==="
    python validation/coord_shell_bsa.py "$PDB" || true
    echo "PDB for viewing: $PDB"
fi
