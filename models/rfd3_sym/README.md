# rfd3_sym — helical / screw symmetry for RFD3

Stock **RFD3** (RFdiffusion3) only knows the **closed point groups** — cyclic
`C_n`, dihedral `D_n`, and the cages `T / O / I`. Every native symmetry frame is
a *pure rotation* (translation = 0), so the assembly is finite and closed, and
the radius is emergent. A **screw / helical** symmetry is a rotation **plus an
axial rise** that never closes — the geometry of nearly every natural fibre —
and RFD3 has no representation for it (the `input_defined` frame path is a
`NotImplementedError` stub).

`rfd3_sym` adds screw symmetry as a **runtime overlay** — it imports `rfd3` and
patches it at import time; it **never edits RFD3 source**, so it survives RFD3
updates and respects upstream.

## What it does

1. **Inject screw frames behind a `C{n}` id** (`frames.py`) — monkey-patches
   `get_cyclic_frames(n)` to return our screw frames `(R_i, t_i)` so the model's
   pair-bias sees n-fold symmetry while the sampler uses the true screw.
2. **Emergent-radius projection** (`projection.py`) — replaces
   `apply_symmetry_to_xyz_atomwise` so each subunit is the ASU **rotated in
   place + lifted by the axial rise** (`asu @ R_i + i·rise·ẑ`). Crucially it
   preserves the radius the model discovers on its own — *forcing* a radius (the
   first, naive fix) erases that lever and shatters the assembly into detached /
   clashing monomers. Optional layers:
   - **soft `R_target`** — gently pin the radius (controls lumen / hollow-vs-solid),
   - **fold-aware contact controller** — force contact along the *true* lattice
     offsets (works for fractional folds),
   - **analytic close-pack** (`closepack.py`) — impose `(R, rise)` so a central
     subunit's whole groove shell contacts.

## Install

```bash
pip install -e .                      # core (numpy); rfd3 + torch from the host env
pip install -e ".[validation,modal]"  # + gemmi/biotite validators, modal runner
```

## Quickstart

```python
import rfd3_sym

# half-integer (staggered groove) fibre, close-packed geometry derived from size
sym_id, info = rfd3_sym.install_screw_symmetry(
    subunits_per_turn=6.5, n_subunits=16, mode="closepack", subunit_size=26)
# -> sym_id == "C16";  info has the derived twist/rise/R
# now run rfd3 design with  symmetry.id = sym_id  (the patches are live)
```

`runners/run_local.py` (RTX-class GPU) and `runners/run_modal.py` (Modal L40S)
wrap this end-to-end; `runners/double_screw.py` extends a fibre to 2× length
by applying the recovered screw operator `Sⁿ` to a copy.

## Parameter reference

Free inputs are **{subunits_per_turn, subunit length L}**; everything geometric
is *derived*.

| Input | Role |
|---|---|
| `subunits_per_turn` (t) | twist = 360/t. **Half-integer t = N.5 → staggered groove** (subunit nestles between the two turn-up neighbours → contacts n±1, n±⌊t⌋, n±⌊t⌋+1). Integer t = eclipsed stacked rings. |
| `n_subunits` (n) | total chains; use `n_for_full_coordination(t)` = ⌈2t⌉+2 so a central subunit is fully coordinated. |
| `rise` | axial translation/subunit; turn-to-turn stacking. *Derived* in `closepack` mode. |
| `r_target` (R) | screw radius of COMs → lumen / hollow-vs-solid. *Derived* in `closepack` mode. |
| `mode` | `emergent` / `closepack` / `contact`. |
| (RFD3) `length` L | subunit size → lattice scale + SS content. |
| (RFD3) `is_non_loopy=True`, `inference_sampler.kind=symmetry`, `low_memory_mode`, `seed` | structured SS; symmetric sampling; memory; seed (fold + alignment are seed-sensitive). |

## Validators (`validation/`)

| Tool | Reports |
|---|---|
| `analyze_screw.py` | recovers twist/rise, emergent radius, all-atom contacts |
| `coord_shell_bsa.py` | central subunit's coordination-shell BSA by offset (the polymerisation interface) |
| `interface_ss.py` | per-interface SS alignment (helix/sheet + axis angle) |
| `scorecard.py` | one-line verdict: groove-complete AND all-aligned AND clash-free? |
| `bsa_score.py` | total inter-subunit buried surface area |
| `validate_helical.py` | screw-operator correctness (vs the point-group-only validator) |

## Status

**Works:** screw placement; emergent radius (no shatter); continuous hollow
tubes with controllable lumen; turn-to-turn stacking; contact forcing for
integer folds; clean fractional folds via multi-seed; analytic close-pack that
closes the staggered groove.

**Open:** **interface secondary-structure alignment in *all* groove directions
at once.** There is currently no input that controls it — it's emergent, a
seed lottery, and trades off against coordination (tight R → loop-contacts;
loose R → under-coordinated). Candidate levers: subunit length `L`,
`select_hotspots` / RASA-buried conditioning, or `is_sheet` (geometrically
ideal but only available in RFD3's legacy dialect). See `docs/`.

## Provenance

Pure overlay (monkey-patches): RFD3 source (vendored in `MolCore/foundry`) is
unmodified. Built by reverse-engineering RFD3's symmetry path; the full
development trail, design rationale, and validation results are in
`docs/REPORT_RFD3_screw_symmetry.md`.
