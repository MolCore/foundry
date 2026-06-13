# rfd3_sym — progress & context log

**Living record** of the screw-symmetry effort: decisions, findings, current
state, and open follow-ups — so anyone (or a future session) can resume with
full context. Append significant items here. Polished technical detail lives in
`REPORT_RFD3_screw_symmetry.md`; this file is the running log.

_Last updated: 2026-06-13._

---

## Goal

Design protein **fibers** (helical filaments / hollow tubes) with RFD3. End
goal: a coherent, self-propagating fiber where a central, fully-coordinated
subunit makes **real, buried, secondary-structure-aligned interfaces with ALL
its groove neighbours** (lateral n±1 + the two turn neighbours n±⌊t⌋, n±⌊t⌋+1),
**clash-free** — i.e. a true 2-D-lattice tube, not a stack of glancing contacts.

## Parameter glossary

| Symbol | Meaning |
|---|---|
| **L** (`subunit_length`) | residues per **single subunit/chain** (monomer size). Not fiber length, not total. Sets lattice scale + SS content. Free input. |
| **t** (`subunits_per_turn`) | twist = 360/t. **Half-integer t = N.5 → staggered groove** (subunit nestles between the two turn-up neighbours). Free input. |
| **n** (`n_subunits`) | total chains. Need ≥ ⌈2t⌉+2 for a fully-coordinated central subunit. Total residues = n·L. |
| **rise** | axial translation per subunit. Derived (close-pack) or set. |
| **R** (`r_target`) | screw radius of subunit COMs → lumen / hollow-vs-solid. Derived (close-pack). |
| twist | derived = 360/t. |
| mode | `emergent` / `closepack` / `contact`. |

## Significant findings (chronological)

1. **RFD3 has no screw symmetry** — only closed point groups C/D/T/O/I; every
   native frame is a pure rotation (t=0); `get_frames_from_file` (input_defined)
   is `raise NotImplementedError`. (source-confirmed)
2. First TMV attempts **exploded** (Rg 875 Å) — the ASU centroid wanders mid-
   diffusion and a radial `t` smears the chains.
3. Centroid-subtract projection placed subunits on the **exact** screw but gave
   **detached/clashing monomers** — *placement ≠ assembly*.
4. **Root cause:** forcing the radius erases the **emergent radius** the model
   needs to form interfaces. The sampler denoises the full assembly, so it can
   design against neighbour coordinates — the fix is geometric, not a model wall.
5. **Emergent-radius projection** (`asu @ R + i·rise·ẑ`, rotate in place + axial
   rise) → works; the model picks the radius.
6. **Rise scale:** 5 nm/subunit → open/detached (too large); protein-scale rise
   → bonded lateral contacts.
7. **Continuous fiber needs turn-stacking:** pitch (n·rise) ≈ subunit height, so
   `rise = h/n`. Fixed the "spiral ribbon → tube" problem.
8. **R_target soft spring** controls radius/lumen to ±0.3 Å → solid vs hollow.
9. **Contact forcing:** RFD3 sampler has **no gradient/potential hook**; built a
   projection-step contact controller — v1 (integer folds) → v2 (fold-aware,
   measures real neighbour gaps, works for fractional).
10. **Fold geometry (group theory):** half-integer t = the staggered groove
    (n centred between n+⌊t⌋ and n+⌊t⌋+1); t = N.5 ⟺ a 2-start (p/2) helix.
    (numerically verified)
11. **Nucleation:** half-integer (2-start) avoids a closed-ring kinetic trap and
    gives cooperative, processive, seamless growth — the "proper" fiber regime.
12. **SS conditioning:** dialect-2 exposes no β flag (only `is_non_loopy`);
    `is_sheet` is ground-truth-derived (`Add1DSSFeature`) / legacy-spoof only.
13. **β-spine test** (rise 4.8 Å): gives a strong continuous spine (n±1 BSA
    2368 Å², 10× a glancing tube) but **helical, not β** — geometry can't
    override RFD3's helix prior.
14. **Close-pack solve:** analytic (R, rise) closing the staggered groove —
    rise/R = 0.115 for t=6.5.
15. **The all-3-aligned goal — the hard wall:** R sweep (28–31) and L sweep
    (50–130), multi-seed, ~56 structures →
    **`{groove-complete, all-aligned, clash-free}` = any TWO, never all three.**
    Groove+aligned cases clash hard (RFD3 clash 118–451); clash-free cases
    aren't aligned (or unfold). **Subunit/interface-design limited, not geometry.**
    L improved coordination (groove=Y 2/4 → 4/4) but not the trade-off.
16. **VRAM** (L40S, low_memory): ≈ 5.6·(res/700)^1.7 GB → **max ≈ 2300 residues**;
    full attention OOMs above ~500 res even on 48 GB.
17. **Interface conditioning (hotspots/RASA) needs an input structure.** Probe:
    adding `select_buried` to a length-only symmetric design fails at parse with
    `"Atom array input must be provided before parsing selections"`. These are
    target/PPI tools (`select_buried→rasa_bin=0`, `select_hotspots→is_atom_level_hotspot`)
    and reference residues of an INPUT pdb — they **cannot condition de-novo
    symmetric generation**. The only route is a **two-pass**: feed a prior fiber
    as input, mark its interface residues buried/hotspot, and **partial-diffuse**
    (`partial_t`) to refine — a more complex pipeline (partial diffusion +
    symmetric input + conditioning + the overlay patches) of uncertain composition,
    not yet built.

## Current state

- **Works:** screw placement; emergent radius (no shatter); continuous hollow
  tubes with controllable lumen; turn-to-turn stacking; contact forcing
  (integer folds clean; fractional via multi-seed); analytic close-pack groove.
- **Open (the wall):** all groove interfaces SS-aligned **and** clash-free at
  once. It's a subunit/interface-design problem now, not geometry.
- **Code home:** `rfd3_sym` overlay → `MolCore/foundry` branch `rfd3_sym`
  (`models/rfd3_sym/`, off `production`), checked out at
  `/home/arielbs10/molCore/projects/foundry-rfd3_sym`. RFD3 source unmodified.

## Open follow-ups / next levers (ranked)

1. **Accept a 2-of-3 corner** (e.g. clean+grooved tube) → **ProteinMPNN + relax**
   for sequence/interface chemistry. The pragmatic path to a usable designed
   fiber now. *Recommended.*
2. **Two-pass interface conditioning** — input a prior fiber, `select_buried`/
   hotspots on its interface residues, `partial_t` to refine. The ONLY way to use
   RASA/hotspots (they need an input structure; finding 17). Uncertain it composes
   with the symmetry overlay; a research gamble.
3. **β route** — a twisted β-sheet packs clash-free + aligns at any twist (the
   natural fiber answer); blocked by `is_sheet` being legacy-dialect only.
4. Native integration (the 4 touchpoints) if/when upstreaming to RFD3.

NOTE: de-novo interface conditioning (`select_hotspots`/RASA on a length-only
symmetric chain) is NOT possible — finding 17. Geometry levers (R, L) are
exhausted (finding 15). The all-3-aligned wall is a subunit/interface-design
problem with no clean de-novo knob in RFD3.

## Standing decisions / conventions

- **Overlay, not a fork** of RFD3 — survives RFD3 updates; no upstream edits.
- Homed as branch `rfd3_sym` in **MolCore/foundry**, off `production`.
- **Test naming = generation parameters:** `spt{t}_R{R}_L{L}_n{n}` (`_ctc` for
  contact mode; fractional t uses `p`, e.g. `spt3p5`).
- **On finishing any job, state full absolute paths** to output PDBs + score reports.
- **RFD3's own clash metric is authoritative** — the scorecard's all-atom
  threshold under-counts residue-level clashes (a 451-clash structure read as
  "4"); always cross-check `n_clashing.*`.
