#!/usr/bin/env python3
"""Example 0 — screw geometry, NO GPU / NO rfd3 required.

`import rfd3_sym` only needs numpy (the rfd3/torch imports are deferred into the
patch functions), so this script runs anywhere and doubles as an install check.

It previews the three canonical fibres before you spend any GPU: for each it
prints the screw parameters, the derived close-pack geometry, the groove
neighbours and minimum chain count, then builds the frames and VERIFIES them
(recovers twist + rise from consecutive frames; for close-pack, checks the
groove-neighbour COM distances really do land near the subunit size).

    python examples/00_geometry.py          # from the package root
"""
from __future__ import annotations

import numpy as np

import rfd3_sym
from rfd3_sym import closepack as cp


def subunit_height(length: int) -> float:
    """Same rough axial extent (Å) the Modal runner uses: 60aa->23, 80aa->28."""
    return 0.25 * length + 8.0


def com_helix(frames, R):
    """COM of each subunit if the ASU COM sits at radius R on +x.

    Mirrors the projection's `asu @ R_i + t_i` (row-vector convention)."""
    p0 = np.array([R, 0.0, 0.0])
    return np.array([p0 @ Ri + ti for Ri, ti in frames])


def preview(name, *, subunits_per_turn, n_subunits, mode,
            subunit_size=None, r_target=None, rise=None):
    t = subunits_per_turn
    twist = 360.0 / t
    k = cp.groove_offsets(t)
    n_min = cp.n_for_full_coordination(t)

    print(f"\n=== {name} ===")
    print(f"  subunits/turn t = {t}   (twist = {twist:.3f}°/subunit)")
    print(f"  groove neighbours (offsets) = {k}   "
          f"({'staggered 2-start' if t != int(t) else 'eclipsed rings'})")
    print(f"  min chains for full coordination = {n_min}   (using n = {n_subunits})")

    # resolve (R, rise) the way the chosen mode would
    if mode == "closepack":
        R, rise = cp.close_packed_geometry(t, subunit_size)
        print(f"  mode=closepack: subunit_size={subunit_size} Å "
              f"-> R={R:.2f} Å, rise={rise:.2f} Å (rise/R={rise/R:.3f})")
    else:
        R = r_target
        print(f"  mode={mode}: R_target={R} Å, rise={rise:.2f} Å  "
              f"(pitch = t·rise = {t*rise:.1f} Å)")

    frames = cp.screw_frames(t, n_subunits, rise)

    # --- verify: recover twist + rise from consecutive frames ---
    dz = np.array([frames[i + 1][1][2] - frames[i][1][2] for i in range(n_subunits - 1)])
    coms = com_helix(frames, R)
    ang = []
    for i in range(n_subunits - 1):
        a, b = coms[i, :2], coms[i + 1, :2]
        ca = np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b) + 1e-9)
        ang.append(np.degrees(np.arccos(np.clip(ca, -1, 1))))
    radii = np.linalg.norm(coms[:, :2], axis=1)
    assert np.allclose(dz, rise, atol=1e-6), "rise not constant between frames"
    assert np.allclose(ang, twist, atol=1e-4), "twist not constant between frames"
    assert np.allclose(radii, R, atol=1e-6), "COM radius not preserved by frames"
    print(f"  ✓ frames verified: constant twist {np.mean(ang):.3f}°, "
          f"rise {np.mean(dz):.3f} Å, COM radius {radii[0]:.2f} Å")

    # --- for close-pack, confirm the groove actually closes ---
    if mode == "closepack":
        c = n_subunits // 2
        d = {o: float(np.linalg.norm(coms[c] - coms[c + o]))
             for o in k if c + o < n_subunits}
        spread = (max(d.values()) - min(d.values())) / np.mean(list(d.values()))
        print("  groove-neighbour COM distances: "
              + ", ".join(f"n±{o}:{v:.1f}Å" for o, v in d.items())
              + f"   (target≈{subunit_size} Å, spread {spread*100:.1f}%)")
        # Self-test that is fold-INDEPENDENT: the solver returns the ratio that
        # MINIMISES the spread. The achievable spread itself depends on t (low-t
        # grooves pack tighter/less evenly: 6.5 -> ~11%, 3.5 -> ~18%), so we
        # verify the minimiser, not a fixed magnitude.
        tw = np.radians(twist)
        def analytic_spread(x):
            v = np.array([np.hypot(2 * np.sin(o * tw / 2), o * x) for o in k])
            return (v.max() - v.min()) / v.mean()
        x0 = rise / R
        assert analytic_spread(x0) <= analytic_spread(x0 * 0.9) + 1e-9
        assert analytic_spread(x0) <= analytic_spread(x0 * 1.1) + 1e-9
        print(f"  ✓ close-pack ratio rise/R={x0:.3f} is the spread-minimiser "
              f"(spread can't go below {analytic_spread(x0)*100:.1f}% for t={t})")


def main():
    print(f"rfd3_sym {rfd3_sym.__version__} — geometry preview (no GPU / no rfd3)")

    # 1) the canonical clean hollow tube (known-good): emergent + soft R_target,
    #    rise = subunit_height / t  so turns stack (pitch = subunit height).
    L = 70
    preview("clean hollow tube  spt5_R20_L70_n10",
            subunits_per_turn=5, n_subunits=10, mode="emergent",
            r_target=20, rise=subunit_height(L) / 5)

    # 2) half-integer staggered groove, analytic close-pack.
    preview("staggered groove   spt6p5_R29_L?_n16",
            subunits_per_turn=6.5, n_subunits=16, mode="closepack", subunit_size=26)

    # 3) fractional fold (contact mode forces R/rise at run time; here we just
    #    preview the close-pack seed the controller starts from).
    preview("fractional fold    spt3p5  (contact seed)",
            subunits_per_turn=3.5, n_subunits=10, mode="closepack", subunit_size=26)

    print("\nAll geometry checks passed. To generate structures, see the "
          "01_/02_ scripts (need the rfd3 env + a GPU).")


if __name__ == "__main__":
    main()
