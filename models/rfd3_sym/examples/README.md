# rfd3_sym examples

Runnable examples, smallest prereq first. Each generation script **prints the
full path** to its output PDB/CIF + provenance and scores the result, per the
project conventions. Outputs go to `examples/outputs/<tag>/` (git-ignored).

> Naming follows the project convention `spt{t}_R{R}_L{L}_n{n}` (`_ctc` for
> contact mode; fractional `t` written with `p`, e.g. `spt3p5`) — the tag *is*
> the generation parameters.

| # | Script | Needs | Demonstrates |
|---|---|---|---|
| 0 | `00_geometry.py` | **nothing** (numpy only) | screw geometry, close-pack solve, frame verification — and an install check |
| 1 | `01_hollow_tube_local.sh` | rfd3 env + local GPU | the canonical clean **hollow tube** (`spt5_R20_L70_n10`) |
| 2 | `02_staggered_groove_modal.sh` | `modal` (MolCore ws) | **half-integer staggered groove**, close-packed (`spt6.5`, n=16) on L40S |
| 3 | `03_fractional_contact_local.sh` | rfd3 env + local GPU | **fold-aware contact controller** on a fractional fold (`spt3.5`) |
| 4 | `04_extend_2x.sh` | **nothing** (numpy only) | extend any generated fibre to **2× length** (post-process) |

## 0 — geometry only (start here)

No GPU, no `rfd3` — `import rfd3_sym` needs only numpy. Previews the three
canonical fibres (twist, derived `R`/`rise`, groove neighbours, min chains),
builds the frames and self-verifies them. Also the fastest way to confirm your
install:

```bash
python examples/00_geometry.py
```

Expect `All geometry checks passed.` It also shows *why* low-`t` staggered
grooves pack less evenly (the close-pack solver returns the spread-minimising
`rise/R`, but the achievable spread depends on `t`).

## Install (for the GPU examples)

```bash
pip install -e ".[validation]"     # overlay + gemmi/biotite scorers
pip install -e ".[validation,modal]"   # + modal, for example 2
```

`rfd3` (`rc-foundry[rfd3]`) and `torch` come from the RFD3 host environment and
are not pinned here (the overlay tracks the host install). The local examples
expect the checkpoint at `~/.foundry/checkpoints/rfd3_latest.ckpt` (or pass
`--ckpt-path` to `run_local.py`).

## 1 — clean hollow tube (local GPU)

```bash
bash examples/01_hollow_tube_local.sh           # SEED=0 OUT=examples/outputs by default
SEED=2 bash examples/01_hollow_tube_local.sh     # different seed
```

`spt5_R20_L70_n10`: 5 subunits/turn, radius softly pinned to 20 Å, 70-aa
subunits, 10 chains, `rise = subunit_height/5` so turns stack into a continuous
wall. ~700 residues total → fits an RTX-class card under `low_memory_mode`.
Prints the output CIF/PDB paths and a one-line `scorecard`.

## 2 — half-integer staggered groove (Modal L40S)

```bash
bash examples/02_staggered_groove_modal.sh
```

`spt6.5`, n=16: a 2-start helix; each subunit nestles into the groove between
its two turn neighbours (offsets `{1,6,7}`). Close-pack geometry `R≈29 Å,
rise≈3.31 Å` (from `closepack.close_packed_geometry(6.5, 26)`) puts the whole
groove shell in contact. Runs on the `foundry-rfd3-tube` app, writes to the
`sym-rfd3-tube-results` volume, **pulls results back locally**, then scores
them (`scorecard` + coordination-shell BSA).

## 3 — fractional fold, contact controller (local GPU)

```bash
bash examples/03_fractional_contact_local.sh
for s in 0 1 2 3; do SEED=$s bash examples/03_fractional_contact_local.sh; done  # seed sweep
```

`spt3.5` packs along `{1,3,4}` — `--contact-mode` measures real neighbour gaps
each step and drives `R`/`rise` to force both interface classes into contact
(`R`/`rise` are derived; `--rise` only seeds the initial placement). Fractional
folds are seed-sensitive — sweep seeds and keep the best-scoring one.

## 4 — extend to 2× length (post-process)

```bash
bash examples/04_extend_2x.sh examples/outputs/spt5_R20_L70_n10/*model_0.pdb
```

Recovers the per-subunit screw operator `S` (Kabsch on chains 0→1) and applies
`Sⁿ` to a whole copy so the second segment continues the helix seamlessly.

## Reading the scores

- **`scorecard.py <pdb> <t>`** — one line: `groove` (central subunit contacts
  all of `{1,⌊t⌋,⌊t⌋+1}`?), `all_aligned` (every groove interface has matched
  SS + small axis angle?), `clash`. `BOTH=*** YES ***` only if all three hold.
  Current results hit **any two of the three** (PROGRESS.md finding 15).
- **`coord_shell_bsa.py <pdb>`** — buried surface area of the central subunit's
  interfaces by offset (is the polymerisation interface real, not glancing?).
- **`interface_ss.py <pdb> [cut] [atol]`** — per-interface SS alignment detail.
- **RFD3's own `n_clashing.*`** in the run output is authoritative for clashes;
  the scorecard's all-atom proxy under-counts (see PROGRESS.md).

See `../docs/` for the design (`REPORT_RFD3_screw_symmetry.md`), the exact
stock-vs-branch diff (`CHANGES_vs_RFD3.md`), and the running log (`PROGRESS.md`).
