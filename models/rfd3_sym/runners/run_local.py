"""Local RFD3 helical-screw generation with EMERGENT radius.

Screw operator:  subunit_i = asu_xyz @ R(i·twist) + i·rise·ẑ
    - twist  = 360 / subunits_per_turn   (degrees)
    - rise   = axial translation per subunit (Å)
    - radius = EMERGENT (model chooses it to pack neighbours)

Difference from the (failed) `run_rfd3_helical_patched_local.py`:
    that runner used radial frames (radius baked into t) + the
    centroid-subtract projection patch, which pinned the radius and gave
    detached monomers. This one uses axial-only frames + the emergent-radius
    projection patch (`prism_helical_emergent_patch`).

Usage:
    uv run python run_rfd3_screw_emergent.py \
        --subunits-per-turn 3.5 --rise 50 --n-subunits 7 \
        --subunit-length 80 --tag c3p5_r50 --out-dir ./outputs/screw_emergent
"""

from __future__ import annotations

import argparse
import json
import sys
import tempfile
from pathlib import Path

import numpy as np


def build_axial_screw_frames(subunits_per_turn, rise, n_subunits, axis=(0, 0, 1)):
    """frames[i] = (R(i·twist) about axis, i·rise·axis). AXIAL translation only."""
    axis = np.asarray(axis, float) / np.linalg.norm(axis)
    twist = 2 * np.pi / subunits_per_turn  # radians per subunit

    def rodrigues(a, th):
        c, s = np.cos(th), np.sin(th)
        K = np.array([[0, -a[2], a[1]], [a[2], 0, -a[0]], [-a[1], a[0], 0.0]])
        return np.eye(3) + s * K + (1 - c) * (K @ K)

    frames = []
    for i in range(n_subunits):
        R = rodrigues(axis, twist * i)
        t = (i * rise) * axis  # axial only — NO radial component
        frames.append((R, t))
    return frames


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--subunits-per-turn", type=float, required=True)
    ap.add_argument("--rise", type=float, required=True, help="Å per subunit")
    ap.add_argument("--n-subunits", type=int, required=True)
    ap.add_argument("--subunit-length", type=int, default=80)
    ap.add_argument("--tag", type=str, required=True)
    ap.add_argument("--out-dir", type=Path, required=True)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--r-target", type=float, default=None,
                    help="soft radial target (Å); omit for pure emergent radius")
    ap.add_argument("--radius-bias", type=float, default=0.3,
                    help="fraction toward R_target per projection step")
    ap.add_argument("--contact-mode", action="store_true",
                    help="force lateral (n±1) + turn-to-turn (n±spt) contact; R and rise derived")
    ap.add_argument("--lateral-overlap", type=float, default=0.9)
    ap.add_argument("--axial-overlap", type=float, default=0.9)
    ap.add_argument(
        "--ckpt-path",
        type=str,
        default=str(Path.home() / ".foundry/checkpoints/rfd3_latest.ckpt"),
    )
    args = ap.parse_args()
    out_dir = args.out_dir / args.tag
    out_dir.mkdir(parents=True, exist_ok=True)

    sys.path.insert(0, str(Path(__file__).parent))

    n = args.n_subunits
    twist_deg = 360.0 / args.subunits_per_turn
    frames = build_axial_screw_frames(args.subunits_per_turn, args.rise, n)
    print(
        f"[screw] {args.subunits_per_turn}/turn → twist {twist_deg:.3f}°, "
        f"rise {args.rise} Å, n={n} (sym_id=C{n}), emergent radius"
    )
    print(f"[screw] frame 1 t={frames[1][1]}  frame {n-1} t={frames[-1][1]}")

    # via_cn: model sees C{n} conditioning + initial placement uses our frames
    from rfd3_sym.frames import install_helical_via_cn_patch
    install_helical_via_cn_patch(n=n, helical_frames=frames)

    # emergent-radius screw projection (optionally soft R_target, or contact-forced)
    from rfd3_sym.projection import install_emergent_screw_patch
    install_emergent_screw_patch(
        frames, r_target=args.r_target, radius_bias=args.radius_bias,
        contact_mode=args.contact_mode, subunits_per_turn=args.subunits_per_turn,
        lateral_overlap=args.lateral_overlap, axial_overlap=args.axial_overlap)
    if args.contact_mode:
        print(f"[screw] CONTACT mode: lateral_overlap={args.lateral_overlap} axial_overlap={args.axial_overlap}")
    elif args.r_target is not None:
        print(f"[screw] soft radius target = {args.r_target} Å (bias {args.radius_bias})")

    design_name = f"screw_{args.tag}"
    design_spec = {
        design_name: {
            "length": args.subunit_length,
            "is_non_loopy": True,
            "symmetry": {"id": f"C{n}", "is_symmetric_motif": True},
        }
    }
    with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as f:
        json.dump(design_spec, f)
        input_json = f.name

    import rfd3.cli as _cli

    orig_argv = list(sys.argv)
    sys.argv = [
        "rfd3", "design",
        f"out_dir={out_dir}",
        f"inputs={input_json}",
        f"ckpt_path={args.ckpt_path}",
        "inference_sampler.kind=symmetry",
        "diffusion_batch_size=1",
        "n_batches=1",
        "low_memory_mode=True",
        "dump_trajectories=False",
        "skip_existing=False",
        "prevalidate_inputs=True",
    ]
    try:
        try:
            _cli.app()
        except SystemExit as e:
            if e.code not in (None, 0):
                raise
    finally:
        sys.argv = orig_argv
        Path(input_json).unlink(missing_ok=True)

    # provenance
    prov = {
        "spec": {
            "subunits_per_turn": args.subunits_per_turn,
            "twist_deg": twist_deg,
            "rise_A": args.rise,
            "n_subunits": n,
            "subunit_length": args.subunit_length,
            "radius": "emergent",
            "sym_id_given": f"C{n}",
        },
        "patches": ["via_cn (C{n} disguise)", "emergent_screw (axial-rise, emergent radius)"],
    }
    (out_dir / f"{args.tag}_provenance.json").write_text(json.dumps(prov, indent=2))
    print(f"[screw] done → {out_dir}")
    for p in sorted(out_dir.glob("*.cif.gz")):
        print("   ", p.name)


if __name__ == "__main__":
    main()
