# Screw (helical) symmetry in RFD3 — end-to-end report

**Date.** 2026-06-10. **Author.** sym project.
**Scope.** Enabling **helical / screw** symmetric generation in RFD3, which
natively supports only the point groups (C_n, D_n, T, O, I). Covers the
challenges, the development arc, the validated results, the inverse-design
recipe, the compute envelope, and what remains.

> Consolidates and supersedes `RESULTS_helical.md`, `RESULTS_screw_emergent.md`,
> and `RESULTS_rfd3_helix_challenges.md` (moved to `docs/archive/`).

---

## 0. Executive summary

RFD3 does cages out of the box but has **no native screw symmetry**. We added it
with runtime patches (no model retraining, no upstream edits) and now generate
**clean continuous hollow tubes** with **forced lateral *and* turn-to-turn
interfaces**, for **integer and fractional** subunits-per-turn:

- integer folds (3, 5, 6 /turn): fully clean — 0 clashes, good fold, rich contacts
- fractional folds (3.5 = 7/2, 6.2 = 31/5): clean via multi-seed selection
- the symmetry, radius/lumen (solid↔hollow), and inter-subunit contacts are all
  controllable from the design inputs {component size, subunits/turn, radius}

The remaining gap is sequence-level interface chemistry (ProteinMPNN + relax) —
RFD3 produces backbone placement only.

---

## 1. Why cages work out of the box (and helices don't)

Stock RFD3 (`rfd3/inference/symmetry/frames.py`) ships native frame generators
for C_n, D_n, T, O, I. Three properties make them work — and helices violate all
three:

1. **Pure-rotation frames, `t = (0,0,0)`.** Every native frame is a rotation
   about the axis with zero translation; the assembly is one orbit of a finite,
   *closed* point group.
2. **Emergent radius (free).** The model diffuses the ASU off-axis and the
   rotations sweep it into a ring/shell at whatever radius makes good
   interfaces — the model controls it, and interfaces form *because* the closed
   geometry forces subunits adjacent.
3. **In-distribution conditioning.** Integer fold ↔ the categorical `sym_id`
   embedding + pair bias the model was trained on.

---

## 2. The seven challenges

| # | Challenge | Cage | Helix | Fix |
|---|---|---|---|---|
| 1 | **Frame input** | native generators | `get_frames_from_file` = `raise NotImplementedError` | `via_cn` patch: monkey-patch `get_cyclic_frames(n)` to return screw frames; declare `sym_id="C{n}"` |
| 2 | **Translation** | `t=0` | screw = rotation **+ axial rise** (`t≠0`); projection math supports `t` but it's never exercised | supply axial-`t` frames |
| 3 | **Radius** | emergent, free | forcing radius into `t` + recentering ASU **erases** the emergent radius → detached/clashing | emergent-radius projection (rotate ASU in place + axial rise only); soft `R_target` for control |
| 4 | **Fold / closure** | integer, closes | fractional subunits/turn (TMV 16.33) never closes; no integer `C_n` describes it | use the true fold (denom of twist/360) as `sym_id`; model designs vs coordinates so tolerates the mislabel |
| 5 | **Growth coupling** | single closed shell | a fibre must **stack turns**: subunit n must contact n±(subunits/turn), needing `pitch = n·rise ≈ component height` → **rise = h/n derived, not free** | derive `rise = h(L)/n` |
| 6 | **Interface forcing** | closed geometry forces adjacency | RFD3 sampler has **no gradient/potential hook** (`assert not X_L.requires_grad`) | projection-step **fold-aware contact controller** |
| 7 | **Size / memory** | one shell fits easily | continuous fibre needs ≥2 turns (≈2·spt+2 subunits) → large residue count | neighbor attention (`low_memory_mode`) + L40S 48 GB |

---

## 3. Development arc (what was tried, what was learned)

### 3.1 First attempts → explosion
`helical_modal.py` (`input_defined` frames) and `helical_modal_cn.py` (Cn-disguise)
both exploded: **Rg 875 Å, 1308 chainbreaks, 0 % SS**. Root cause: the projection
rebuilds chains as `X_asu @ R_i + t_i` without recentering; mid-diffusion the ASU
centroid wanders ~200–300 Å (c0≈2560 Å noise), so with `t_i` at ~80 Å radius the
chains smear over hundreds of Å. (Harmless for cages where `t_i=0`.)

### 3.2 Centroid-subtract projection → exact placement, but NOT an assembly
`prism_helical_projection_patch` subtracts the ASU centroid before `R_i`, then
adds absolute `t_i`. The TMV_full run (17×80, twist 22.04°, rise 1.408, r=80)
then placed subunits on the **exact requested screw**:

| metric | failed TMV | TMV_full (projfix) | T-cage ref |
|---|---|---|---|
| max Cα deviation | 35.4 Å | 0.457 Å | 0.50 Å |
| chainbreaks | 1308 | 0 | 0 |
| radius of gyration | 875 Å | 81.5 Å | 23 Å |
| screw twist/rise/radius | — | 22.04°/1.408 Å/79.97 Å (exact) | — |

**But it is a ring of detached/clashing monomers, not an assembly**: 125/136
subunit pairs >5 Å apart, 7 clashing, **zero designed interfaces**. Lesson:
**placement ≠ assembly.** The centroid-subtract pins every subunit to the fixed
r=80, erasing the emergent radius the model needs to pull subunits into contact.

### 3.3 Source trace — a fixable projection bug, not an architecture wall
- The sampler denoises the **full assembly** (`inference_sampler.py:397/451/479`),
  so the model designs against neighbour **coordinates** — it can pack against any
  geometry, screw included.
- The projection already uses `t` (`symmetry_utils.py:372`, `asu@R + t`).
- So the only thing wrong was the patch erasing the emergent radius.

### 3.4 Emergent-radius fix → it works
`prism_helical_emergent_patch`: `subunit_i = asu_xyz @ R(i·twist) + i·rise·ẑ` —
rotate the ASU **in place** (emergent radius preserved), add **axial rise only**,
no centroid-subtract, no radial offset. The model now chooses the radius; 0
clashes. Validated at 3, 5, 3.5 /turn (twist/rise recovered exactly).

### 3.5 Rise scale, and the turn-stacking coupling
- `rise = 5 nm/subunit` (50 Å) → an **open** helix: minimum subunit spacing is
  50 Å, which 80-aa subunits can't bridge → a string of monomers (geometry, not
  a method failure).
- protein-scale rise → bonded **lateral** contacts.
- but the first "tubes" were **spiral ribbons** (lateral-only, 0 turn-to-turn) —
  because `pitch (n·rise) ≫ subunit height`, so turns don't stack. **Fix:
  `rise = h/n`** (pitch ≈ subunit height) → turns bond → a *continuous* tube
  (`spt5_R20_L70_n10`: lateral **and** turn-to-turn contacts, lumen 7.3 Å,
  BSA 10,135 Å², 0 chainbreaks).

### 3.6 Radius control → solid vs hollow
The emergent radius is erratic (5.7–39 Å across folds/rises) so topology can't
be specified. Added a **soft `R_target` radial spring** (radial-only nudge, so it
hits the target without erasing design). Radius lands within ±0.3 Å of target:

| fold | R_target | radius | lumen | topology |
|---|---|---|---|---|
| 3/turn | 8 → 8.1 | | 2.0 | solid |
| 3/turn | 20 → 20.0 | | 11.8 | HOLLOW |
| 3/turn | 30 → 30.0 | | 10.6 | HOLLOW |
| 5/turn | 12 → 12.0 | | 2.3 | solid |

→ `R_target` is the design input for lumen / solid-vs-hollow.

### 3.7 Forcing contact (challenge 6) — fold-aware controller
RFD3 has no potential hook, so contact is forced in the **projection step**.
- **v1** set `R = α·w/(2 sin(π/spt))`, `rise = β·h/spt` (α=β=0.9) from the
  measured subunit width/height. Clean for **integer** folds; **fractional**
  clashed (assumes turn-neighbour at `i+round(spt)`, false for 7/2, 31/5).
- **v2 (fold-aware):** each step, measure the ASU's gap to **every** subunit,
  classify lateral (|wrapped angle| ≥ 45° → R) vs axial (< 45° → rise), drive the
  nearest gap in each class to a ~4 Å contact target with a 2.6 Å clash floor
  (feedback; R,d are state). Forces contact along the **true** lattice offsets.

5 examples (contact counts = pairs <5 Å by |i−j| offset):

| test | spt | contact offsets (count) | clash<2Å | RFD3 clash | helix |
|---|---|---|---|---|---|
| spt3_L70_n8_ctc | 3 | 1:7, 3:5 | 0 | 0 | 0.83 |
| spt5_L70_n12_ctc | 5 | 1:11, 5:7 | 0 | 0 | 0.85 |
| spt6_L70_n14_ctc | 6 | 1:13, 5:9, 6:8 (30) | 0 | 0 | 0.81 |
| spt3p5_L70_n9_ctc | 3.5 | 3, 4, 7 | (seed-dep) | 0 | (seed-dep) |
| spt6p2_L70_n15_ctc | 6.2 | 1, 6 | (seed-dep) | 0 | (seed-dep) |

### 3.8 Multi-seed → clean fractional folds
Fractional fold *quality* is seed-sensitive (the offsets/registration are
already correct). 6 seeds each → clean winners:

| fold | seed | breaks | clash (both) | helix | contacts | BSA/sub |
|---|---|---|---|---|---|---|
| 3.5 (7/2) | 2 | 0 | **0** | **0.89** | 8 (3-start + 7 turn-repeat) | 37 Å² |
| 6.2 (31/5) | 5 | 0 | **0** | **0.86** | 23 (1-start + 6-start) | 133 Å² |

Both integer and fractional subunits/turn now produce clean continuous tubes.
The 7/2 lattice is intrinsically sparse (low BSA); 31/5 packs denser.

---

### 3.9 Continuous-growth framing & the spine interface

A screw fibre is not an oligomer with discrete dimer interfaces — it is an
**open polymer that grows by adding one monomer through a single repeating
interface**. The incoming monomer docks into one composite site formed by both
its sequence-neighbour (n±1) and its turn-neighbour (n±spt), tied by the screw;
the monomer must be **head-to-tail self-complementary** under the screw
operator (a polymerising building block, like actin/amyloid), not a tiled dimer.

The right figure of merit is therefore the **coordination-shell BSA** of a
central, fully-coordinated subunit (`validation/coord_shell_bsa.py`) — the total
buried area it makes with its whole shell — not pairwise dimer BSA.

Measured asymmetry on the contact-forced tubes: interfaces are uneven across
directions *and* all small — e.g. `spt6` central-subunit shell = **753 Å²**
(n±1 234, n±5 186, n±6 333), i.e. glancing touches, not buried interfaces (a
real interface is 600–1000+ Å²). A rigid monomer can only make one direction
complementary.

**Fix = a continuous secondary-structure spine in the growth direction**, set by
matching the rise to the SS register. The **β-spine test** (rise = 4.8 Å, the
cross-β register, small flat monomer) showed:

| fibre | coord-shell BSA | n±1 (spine) | SS | clash |
|---|---|---|---|---|
| `spt6_L70_n14_ctc` (glancing) | 753 Å² | 234 | helix | 0 |
| `bspine_spt12_L24` (rise 4.8) | **2929 Å²** | **2368 Å²** | helix 0.62 | 0 |

Small rise → a **strong continuous-growth spine** (n±1 buries 2368 Å², ~10× the
glancing tube; whole shell ~4×), 0 clashes — a realistic continuous-growth
filament. **But it came out helical, not β**: geometry (the 4.8 Å slab) does not
compel β — RFD3's helix prior wins, and dialect-2 exposes no β flag (only
`is_non_loopy`). Forcing true cross-β needs the **`is_sheet` SS-conditioning**
that lives in the legacy dialect (an atom-level `is_sheet` annotation + the
SS-conditioning transform) — a deeper plumbing change, not yet wired.

## 4. Inverse-design recipe (target geometry → inputs)

Free inputs **{component size L, subunits/turn (spt), radius R}**; twist, rise are
derived.

- `twist = 360 / spt`
- lateral contact: `R ≈ w / (2·sin(π/spt))`  (w ≈ subunit tangential width, ~25–30 Å)
- turn-to-turn contact: `pitch = spt·rise ≈ subunit height h` → `rise = h/spt`
- `lumen ≈ R − subunit_inner_extent`; **hollow** needs `R` large (spt ≳ 5–6),
  **solid** = low spt (2–3) + small R
- `subunit length L` → wall thickness / scale; for fractional folds also
  **multi-seed** and pick the clean-folding draw
- in **contact mode** R and rise are auto-derived from the measured subunit each
  step (inputs reduce to {L, spt}); for fractional, the controller finds the true
  helical-net offsets

---

## 5. Compute envelope (L40S 48 GB, `low_memory_mode`)

| total residues | peak VRAM |
|---|---|
| 700 (n10×L70) | 5.6 GB |
| 1440 (n12×L120) | 19.2 GB |
| 2400 (n12×L200) | OOM |

`VRAM ≈ 5.6·(res/700)^1.7 GB` → **max ≈ 2300 residues**. For a fully-coordinated
subunit `n ≈ 2·spt + 2`, so **max component length L ≈ 2300/n** (≈190 aa at
spt5/n12). Full attention (`low_memory_mode=False`) OOMs above ~500 res even on
48 GB — neighbor attention is required for fibres. (Local RTX 3090 folds ≤~600
res cleanly; >~700 res breaks backbones.)

---

## 6. Validation methodology

- `validation/analyze_screw.py` — recovers twist/rise (Kabsch between subunits),
  measures the emergent radius, classifies all-atom inter-subunit contacts.
- contact-topology check — contacts by |i−j| offset → distinguishes a continuous
  tube (lateral + turn-to-turn) from a lateral-only spiral.
- `validation/bsa_score.py` — real buried surface area (Shrake–Rupley) =
  interface metric, not mere proximity.
- `validation/validate_helical.py` — screw-operator correctness vs assembly
  quality (the original validator handled only closed point-group orbits).
- Always cross-check RFD3's own metrics (chainbreaks, helix, inter-residue
  clashes) AND the all-atom contact/clash analysis — the screw-placement check
  passes even on a zero-interface ring.

---

## 7. Code & artifacts

| File | Role |
|---|---|
| `scripts/prism_helical_via_cn_patch.py` | `C{n}` conditioning (frame injection) |
| `scripts/prism_helical_emergent_patch.py` | emergent-radius screw + soft `R_target` + fold-aware `contact_mode` |
| `scripts/run_rfd3_screw_emergent.py` | local runner (RTX 3090) |
| `modal_app/tube_modal_emergent.py` | Modal L40S runner; `run` entrypoint, auto param-tags, derived rise, contact mode |
| `validation/{analyze_screw,bsa_score,validate_helical}.py` | validators |
| `outputs/tube/<tag>/...` | structures (`.pdb`, `.cif.gz`), scores (`*_model_0.json`), provenance, PSE, renders |

**Test naming convention:** tags are the generation parameters —
`spt{subunits_per_turn}_R{radius}_L{chain_length}_n{n_chains}`, `_ctc` suffix for
contact-mode (R derived). Fractional spt uses `p` (e.g. `spt3p5_L70_n9_ctc`).

---

## 8. Status & still open

**Done:** challenges 1–7 addressed; clean continuous hollow tubes for integer and
fractional subunits/turn; symmetry, radius/lumen, and contacts controllable.

**Open:**
1. **True β-spine** — wire `is_sheet` SS-conditioning (legacy dialect: set the
   atom-level `is_sheet` annotation + activate the SS-conditioning transform) so
   the continuous-growth spine forms as cross-β, not helix. Geometry alone
   (rise 4.8) gives a strong spine but RFD3 makes it helical.
2. **ProteinMPNN + relax** downstream — turn backbone placement into real
   designed-sequence interfaces (RFD3 = placement only).
2. Denser packing for sparse fractional lattices (e.g. 3.5, BSA 37/sub) if higher
   buried area is wanted — controller could target ≥3 neighbour classes.
3. Native screw conditioning (represent rise+twist in sym features rather than
   `C_n`-disguise) — the "proper" fix; model-level, likely needs retraining.
