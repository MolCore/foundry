#!/usr/bin/env bash
# Example 3 — FRACTIONAL fold with the FOLD-AWARE CONTACT CONTROLLER (local GPU).
#
#   spt3.5, n=10, contact mode : 3.5 subunits/turn (a 7/2 helix) packs along
#   offsets {1,3,4}, NOT {1,3} — so we can't assume the contacting neighbours.
#   `--contact-mode` measures the ASU's real gaps each projection step, bins
#   them lateral vs turn-to-turn by wrapped screw angle, and drives R and rise
#   to put both interface classes in contact (clash floor pushes apart if too
#   close). R and rise are DERIVED by the controller; --rise here only seeds the
#   initial frame placement.
#
# Prereqs: same as example 1 (rfd3 env + GPU + checkpoint). Fractional folds are
# seed-sensitive — sweep a few seeds (SEED=0,1,2,...) and score each.
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PKG="$(dirname "$HERE")"                 # models/rfd3_sym
OUT="${OUT:-$HERE/outputs}"
SEED="${SEED:-0}"

cd "$PKG"
PYTHONPATH="$PKG${PYTHONPATH:+:$PYTHONPATH}" \
python runners/run_local.py \
    --subunits-per-turn 3.5 --rise 6 --n-subunits 10 \
    --subunit-length 70 --contact-mode --seed "$SEED" \
    --tag spt3p5_L70_n10_ctc --out-dir "$OUT"

echo
echo "=== outputs (full paths) ==="
ls -1 "$OUT"/spt3p5_L70_n10_ctc/*.cif.gz "$OUT"/spt3p5_L70_n10_ctc/*provenance.json 2>/dev/null || true

CIF=$(ls "$OUT"/spt3p5_L70_n10_ctc/*model_0.cif.gz 2>/dev/null | head -1 || true)
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
    echo "=== scorecard (offsets {1,3,4} for t=3.5) ==="
    python validation/scorecard.py "$PDB" 3.5 || true
    echo "=== coordination-shell BSA by offset (did the controller force contact?) ==="
    python validation/coord_shell_bsa.py "$PDB" || true
    echo "PDB for viewing: $PDB"
fi
