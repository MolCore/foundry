#!/usr/bin/env bash
# Example 4 — EXTEND a generated fibre to 2x length (post-process, NO GPU).
#
# RFD3 only builds the n chains you asked for. A screw is self-similar, so we can
# recover the per-subunit operator S from the structure (Kabsch on chains 0->1)
# and apply S^n to a whole copy: the second segment continues the helix
# seamlessly across the junction. Pure geometry — no model, no GPU.
#
# Usage:
#   bash examples/04_extend_2x.sh <fiber.pdb> [out_doubled.pdb]
# e.g. on the output of example 1:
#   bash examples/04_extend_2x.sh examples/outputs/spt5_R20_L70_n10/*model_0.pdb
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PKG="$(dirname "$HERE")"                 # models/rfd3_sym

IN="${1:?usage: 04_extend_2x.sh <fiber.pdb> [out.pdb]}"
OUT="${2:-${IN%.pdb}_2x.pdb}"

python "$PKG/runners/double_screw.py" "$IN" "$OUT"
echo "doubled fibre (full path): $OUT"
