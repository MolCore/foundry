# What `rfd3_sym` changes vs. stock RFD3 — enabling screw (helical) symmetry

**Audience:** anyone deciding what is unique to this branch, or upstreaming it into RFD3.
**Scope:** conceptual change + the exact code, file by file, with stock RFD3 line
references. RFD3 source is **unmodified**; everything here is a runtime overlay
(`models/rfd3_sym/`). Companion docs: `REPORT_RFD3_screw_symmetry.md` (full design),
`PROGRESS.md` (running log + open problem).

RFD3 source paths below are relative to the installed package
(`…/models/rfd3/src/rfd3/`); line numbers are from the `production` checkout this
branch forked.

---

## 0. TL;DR

Stock RFD3 generates only the **closed point groups** — Cₙ, Dₙ, T, O, I. Every
native symmetry frame is a **pure rotation** (translation = 0), so the assembly
always closes back on itself. A **screw** (helix/filament/tube) is a rotation
**plus an axial rise** — an open, non-closing symmetry RFD3 has no way to request.

The surprising part, confirmed from source: RFD3's symmetry *machinery* already
supports a per-frame translation through the entire pipeline (frame → annotation
→ feature → projection). What is missing is narrow:

1. **No frame generator ever emits a translation.** `get_cyclic_frames` (and the
   D/T/O/I generators) hardcode `t = (0,0,0)`.
2. **The one general entry point that could carry an arbitrary screw is a stub.**
   `get_frames_from_file("input_defined")` → `raise NotImplementedError`.
3. **A naïve fix shatters the assembly.** If you bake the radius into the frame
   translation (a *radial* offset), every subunit is pinned to that radius and
   the monomers detach. The rise must be **axial-only** so the radius stays
   *emergent* — chosen by the model so it can actually form interfaces.

`rfd3_sym` closes exactly these gaps, as an overlay:

- **`frames.py` patch** — make `get_cyclic_frames(n)` return our **screw** frames
  (rotation + **axial** rise) behind the in-distribution id `C{n}`, so the
  network's conditioning still sees clean n-fold symmetry.
- **`projection.py` patch** — override the per-step symmetry projection to keep
  the ASU at its **emergent radius**, and add two things stock has no hook for:
  a soft **radius target** (lumen / hollow-vs-solid control) and a **fold-aware
  contact controller** (force real interfaces, incl. fractional folds).
- **`closepack.py`** — analytic screw-lattice geometry (no stock equivalent).
- **`install_screw_symmetry(...)`** — one call that wires it all up and hands
  back the `sym_id` (`"C{n}"`) to pass to RFD3.

---

## 1. What stock RFD3 ships (the baseline)

### 1.1 Only closed point groups; every frame is a pure rotation

`get_symmetry_frames_from_symmetry_id` (`inference/symmetry/frames.py:5`) is the
sole dispatch. Its entire vocabulary (≈ lines 21–39):

```python
if   symmetry_id.lower().startswith("c"): frames = get_cyclic_frames(int(id[1:]))
elif symmetry_id.lower().startswith("d"): frames = get_dihedral_frames(int(id[1:]))
elif symmetry_id.lower() == "t":          frames = get_tetrahedral_frames()
elif symmetry_id.lower() == "o":          frames = get_octahedral_frames()
elif symmetry_id.lower() == "i":          frames = get_icosahedral_frames()
elif symmetry_id.lower() == "input_defined":
    frames = get_frames_from_file(sym_conf.symmetry_file)   # <-- stub, see 1.2
else: raise ValueError(f"Symmetry id {symmetry_id} not supported")
```

Every generator returns pure rotations. `get_cyclic_frames` (`frames.py:232`):

```python
def get_cyclic_frames(order):
    frames = []
    for i in range(order):
        angle = 2 * np.pi * i / order
        R = np.array([[ cos, -sin, 0], [ sin, cos, 0], [0, 0, 1]])
        frames.append((R, np.array([0, 0, 0])))   # <-- translation HARDCODED to 0  (line 251)
    return frames
```

The `(R, t)` tuple structure *has* a translation slot — but `t` is always the
zero vector. (`get_dihedral_frames` etc. do the same.) After dispatch, the only
gate is `assert is_valid_rotation_matrix(R)` per frame — it checks `R`, never
`t`. So a translation, if one existed, would not be rejected.

### 1.2 The one general hook is unimplemented

`get_frames_from_file` (`frames.py:531`):

```python
def get_frames_from_file(file_path):
    raise NotImplementedError("Input defined symmetry not implemented")
```

So the `input_defined` path — the natural place to supply an arbitrary
screw/helical transform set — does not exist in stock.

### 1.3 The frame → feature → projection pipeline already carries translation

This is the crucial, non-obvious part. A frame `(R, t)` is **not** discarded down
to rotation; it survives end to end:

- **Encode** — `decompose_symmetry_frame((R, t))` → `RTs_to_framecoords(R, t)`
  (`frames.py:545`): `Ori = t`; `X = Ori + R[0]̂`; `Y = Ori + R[1]̂`. The
  translation **is** the frame origin `Ori`. These pack into the per-atom
  annotations `sym_transform_Ori/X/Y` (`symmetry_utils.py:213`, `atom_array.py:188`).
- **Decode** — `framecoords_to_RTs(Ori, X, Y)` (`frames.py:561`): rebuilds `R`
  from `X−Ori`, `Y−Ori`, and sets `T = Ori`. The translation round-trips
  **exactly**. The reconstructed `{id: (R, T)}` dict becomes the feature
  `sym_transform` (`transforms/symmetry.py:33,79`).
- **Apply** — `apply_symmetry_to_xyz_atomwise` (`symmetry_utils.py:328`), called
  each denoising step from `model/inference_sampler.py:369`:

```python
if not partial_diffusion:                                       # global COM -> origin
    X_L[:, ~fixed_motif_mask, :] -= X_L[:, ~fixed_motif_mask, :].mean(dim=1, keepdim=True)
...
sym_X_L[:, this_subunit, :] = (
    torch.einsum("blc,cd->bld", asu_xyz, sym_transforms[target_id][0])  # R
    + sym_transforms[target_id][1]                                      # + t   (line 372-374)
)
```

It already computes `asu @ R + t`. And because it **re-centres the whole
assembly to the origin** each step (the COM subtract) and the ASU sits *off-axis*,
the **radius is emergent** for free — the model decides how far the ASU sits from
the axis; the projection never imposes one.

**Consequence (the load-bearing insight):** stock RFD3 was one ingredient away
from screws. If `get_cyclic_frames` had emitted an *axial* translation, the
existing machinery would have round-tripped it and `apply_symmetry_to_xyz_atomwise`
would have produced a correct emergent-radius screw — no projection change
needed. The wall is (1.1) + (1.2): nothing ever feeds a translation in, and the
general hook is a stub.

### 1.4 No gradient / potential hook in the sampler

The sampler exposes **no** force/potential/guidance hook on the symmetric
assembly. The per-step projection (`apply_symmetry_to_xyz_atomwise`) is the only
place you can influence inter-subunit geometry. There is therefore no stock way
to *target a radius* or *force a contact* — see §2.3.

---

## 2. The conceptual change

### 2.1 Screw = rotation + **axial** rise, with the radius left emergent

A screw subunit *i* is:

```
subunit_i = ASU @ R(i · twist)  +  i · rise · ẑ        twist = 360° / subunits_per_turn
```

Two non-negotiables, both learned the hard way (PROGRESS.md findings 2–5):

- **The translation must be axial only** (`(0, 0, rise)`), never radial. Baking
  the radius into `t` (`t = R·d̂ + rise·ẑ`) pins every subunit to that exact
  radius regardless of what the ASU wants → detached, clashing monomers. Keep `t`
  axial and the radius **emerges** from the ASU's own off-axis position (which
  stock's COM-subtract already supports, §1.3).
- **Placement ≠ assembly.** Putting subunits on the exact screw is necessary but
  not sufficient; the model must denoise the *whole* assembly so it can design an
  ASU whose surface complements its screw images. Emergent radius is what gives
  it that freedom.

### 2.2 Hide the screw behind a `C{n}` id (stay in-distribution)

RFD3's conditioning features (the `sym_id` embedding, the chain-pair bias) were
trained on point groups. So we **tell the model `C{n}`** (n = number of chains)
— fully in-distribution — but **redefine what `C{n}` *means* geometrically** to
be our screw. The network designs a clean ASU "as if" for `Cₙ`; the sampler's
projection enforces the true screw each step. This cleanly separates *what the
model sees* (standard `Cₙ`) from *what the sampler enforces* (the screw).

### 2.3 Two controls stock cannot express

Because the projection is the only lever (§1.4), the overlay layers two optional
behaviours onto it — neither expressible in stock RFD3:

- **Radius target (`r_target`)** — a soft radial spring nudging the emergent
  radius toward a chosen value → controls lumen size / solid-vs-hollow tube.
- **Fold-aware contact controller (`contact_mode`)** — measures, each step, the
  ASU's real gaps to every neighbour, classifies each as lateral vs. turn-to-turn
  by its wrapped screw angle, and drives the nearest gap in each class to a
  contact target (with a clash floor). This forces the interfaces a *continuous*
  fibre needs, and — by measuring rather than assuming offsets — works for
  **fractional** subunits/turn (e.g. 3.5, 6.5), whose contacting neighbours are
  not at `i ± 1, i ± t`.

### 2.4 Screw-lattice geometry (half-integer groove, close-pack)

A half-integer subunits/turn (t = N.5) gives a **staggered groove** (a 2-start
helix): the central subunit nestles between its two turn neighbours, contacting
offsets `{1, ⌊t⌋, ⌊t⌋+1}`. `closepack.py` solves analytically for the `(R, rise)`
that put all those neighbour distances in contact at once, and for the minimum
chain count `⌈2t⌉+2` needed for one fully-coordinated central subunit.

---

## 3. The code, file by file (`models/rfd3_sym/rfd3_sym/`)

### 3.1 `frames.py` — `install_helical_via_cn_patch(n, helical_frames)`

**Replaces** `rfd3.inference.symmetry.frames.get_cyclic_frames` so that the one
order `n` returns our screw frames; all other orders delegate to the original:

```python
def patched_cyclic(order):
    if order == _INSTALLED_N:        # our fibre's chain count
        return _INSTALLED_FRAMES     # screw frames: (R(i·twist), i·rise·ẑ)
    return _ORIGINAL_CYCLIC(order)   # untouched Cn elsewhere
rfd_frames.get_cyclic_frames = patched_cyclic
```

This is the single change that turns "`C{n}`" from a closed ring into a screw,
while every conditioning feature still reads a normal `Cₙ`. Reversible via
`uninstall()`. **This is the core enabler** — combined with stock §1.3 it already
yields an emergent-radius screw.

### 3.2 `projection.py` — `install_emergent_screw_patch(...)`

**Replaces** `rfd3.inference.symmetry.symmetry_utils.apply_symmetry_to_xyz_atomwise`.
Three modes, selected at install:

- **`emergent`** (default) — same global COM-subtract as stock, then rotate the
  ASU **in place** and lift by the axial rise. Functionally equal to stock §1.3
  *given* the screw frames, with one deliberate difference: it applies the screw
  from the overlay's **own captured frame copy** (`_FRAMES`, keyed by transform
  id) rather than the round-tripped `sym_transform` feature — a belt-and-suspenders
  guarantee the axial rise is exactly what we asked for, and the hook point for
  the next two modes.
- **`r_target`** — after centring the ASU, add a radial nudge
  `radius_bias · (d̂·R_target − r_xy)` (radial component only; axial untouched).
  Soft spring → controllable radius to ≈ ±0.3 Å.
- **`contact_mode`** — the fold-aware controller of §2.3. Seeds `(R, rise)` from
  the analytic close-pack, then each step: build all subunits, measure
  `min‖ASU − neighbour‖` to each, bin by `|wrapped angle|` (≥45° lateral → adjust
  **R**; <45° axial → adjust **rise**), drive the nearest in each bin toward
  `contact_dist` (≈4 Å), push apart below the clash floor (2.6 Å), EMA-smooth.

The geometric core (all modes):

```python
out[:, sub, :] = torch.einsum("blc,cd->bld", asu, R_) + t   # t axial-only
```

**What's unique here vs. stock:** the *basic* emergent screw could ride on stock's
unmodified projection (§1.3). What stock genuinely **cannot** do — and what this
override exists for — is `r_target` and `contact_mode`: there is no other hook
(§1.4) to target a radius or force an interface in the no-gradient sampler.

### 3.3 `closepack.py` — analytic screw-lattice geometry (new; no stock analogue)

- `screw_frames(spt, n, rise, axis)` — the `(R(i·twist), i·rise·axis)` list.
- `groove_offsets(spt)` → `[1, ⌊spt⌋, ⌊spt⌋+1]` — the staggered-groove neighbours.
- `close_packed_geometry(spt, subunit_size)` → `(R, rise)` minimising the spread
  of the groove-neighbour distances (all in contact). E.g. rise/R = 0.115 at t=6.5.
- `n_for_full_coordination(spt)` → `⌈2·spt⌉+2`.

### 3.4 `__init__.py` — `install_screw_symmetry(...)` (one-call API)

Builds the frames, installs both patches, returns `("C{n}", info)`:

```python
sym_id, info = rfd3_sym.install_screw_symmetry(
    subunits_per_turn=6.5, n_subunits=16, mode="closepack", subunit_size=26)
# then run RFD3 with symmetry.id = sym_id   (== "C16")
```

`mode ∈ {emergent, closepack, contact}`; `rise`, `r_target`, `subunit_size`,
`radius_bias`, `contact_dist`, `axis` as needed.

---

## 4. Inputs / parameter model (what you actually specify)

The design spec is an ordinary length-only symmetric RFD3 job; the screw lives
entirely in the patched frames:

```json
{ "screw_x": { "length": L, "is_non_loopy": true,
               "symmetry": {"id": "C{n}", "is_symmetric_motif": true} } }
```

CLI: `inference_sampler.kind=symmetry`, `low_memory_mode=True`, `ckpt_path=rfd3`.

| Input | Meaning | Set by |
|---|---|---|
| **subunits/turn (t)** | twist = 360/t. Half-integer ⇒ staggered groove. | user |
| **n_subunits** | total chains; ≥ `⌈2t⌉+2` for full coordination. | user |
| **rise** | axial Å per subunit. | user, or close-pack |
| **R (`r_target`)** | screw radius → lumen / hollow-vs-solid. | user, or close-pack |
| **L (`length`)** | residues per single chain (lattice scale + SS content). | user |
| **mode** | `emergent` / `closepack` / `contact`. | user |

---

## 5. The exact stock touchpoints a *native* integration would edit

If/when this is upstreamed into RFD3 proper (instead of patched), these are the
edit sites — and because of §1.3 the change is small:

| # | File:line | Stock | Native change |
|---|---|---|---|
| 1 | `inference/symmetry/frames.py:232` `get_cyclic_frames` | `t=(0,0,0)` | accept/emit an axial rise (or add a `get_screw_frames`) |
| 2 | `inference/symmetry/frames.py:531` `get_frames_from_file` | `NotImplementedError` | implement: read a screw/helical spec → `(R, t)` frames |
| 3 | `inference/symmetry/frames.py:5` dispatch (≈21–39) | C/D/T/O/I/input_defined | add a `screw`/`helical` id (twist+rise+optional R) |
| 4 | `…/SymmetryConfig` + input parsing | point-group fields | carry `subunits_per_turn`, `rise`, optional `r_target` |
| 5 | `inference/symmetry/symmetry_utils.py:328` `apply_symmetry_to_xyz_atomwise` | `asu @ R + t`, COM-subtract | **already screw-correct for axial t** — only needs the optional `r_target` / contact hooks if those controls are wanted |
| 6 | `model/inference_sampler.py:369` | calls the projection each step | unchanged |

Note row 5: the projection is already correct for an axial-translation frame.
The minimal native screw is essentially rows 1–4 (feed an axial-rise frame);
row 5 only changes if you want the radius/contact *controls*.

---

## 6. What this does **not** change

- **No network weights, no architecture, no retraining.** SE(3)-equivariance and
  every learned feature are untouched. Screw symmetry is imposed purely as an
  *output constraint* (frames + per-step projection), exactly as the point groups
  already are.
- **No RFD3 source files.** Pure monkey-patch overlay → survives RFD3 updates.
- **Point groups untouched.** Any `C{m≠n}`, `D`, `T`, `O`, `I` job delegates to
  the originals.

---

## 7. Status & honest limitation

**Works:** continuous emergent-radius screws (no shatter); controllable lumen
(solid↔hollow); turn-to-turn stacking; contact forcing (clean for integer folds,
multi-seed for fractional); analytic close-pack.

**Open (PROGRESS.md finding 15):** getting **all** groove interfaces
simultaneously secondary-structure-aligned **and** clash-free. Across an R sweep
(28–31 Å) and L sweep (50–130) — ~56 structures — the result is
`{groove-complete, all-aligned, clash-free}` = **any two, never all three**. This
is now a **subunit/interface-design** problem, not a geometry one: the geometry
levers (R, L, rise, t) are exhausted, and de-novo interface conditioning
(RASA/hotspots) requires an input structure, so it can't condition a length-only
symmetric design (finding 17). The pragmatic path forward is to accept a
two-of-three fibre and pass it to ProteinMPNN + relax for the interface chemistry.

---

*Generated for the `rfd3_sym` branch of MolCore/foundry. Stock line numbers from
the `production` fork point (`98f1ae4`).*
