"""rfd3_sym — helical / screw symmetry overlay for RFD3 (RFdiffusion3).

Stock RFD3 supports only the closed point groups (C_n, D_n, T, O, I) — every
native symmetry frame is a pure rotation (translation = 0). A screw is a
rotation PLUS an axial rise, an open (non-closing) symmetry RFD3 has no notion
of. This package adds it as a *runtime overlay* — no RFD3 source edits:

  1. inject screw frames behind a `C{n}` id (so the model's pair-bias sees
     n-fold symmetry while the sampler uses our screw), and
  2. replace the symmetry projection so the ASU is rotated *in place* + lifted
     by the axial rise — preserving the radius the model discovers on its own
     (forcing a radius shatters the assembly), optionally with a soft radius
     target, a fold-aware contact controller, or the analytic close-pack.

Quickstart
----------
    import rfd3_sym
    sym_id, info = rfd3_sym.install_screw_symmetry(
        subunits_per_turn=6.5, n_subunits=16, mode="closepack", subunit_size=26)
    # then run rfd3 with symmetry.id = sym_id  (= "C16")

See docs/REPORT_RFD3_screw_symmetry.md for the full design, parameters, and the
open problem (interface secondary-structure alignment).
"""
from __future__ import annotations

from .frames import install_helical_via_cn_patch as install_screw_frames
from .projection import install_emergent_screw_patch
from .closepack import (
    screw_frames,
    close_packed_geometry,
    groove_offsets,
    n_for_full_coordination,
)

__version__ = "0.1.0"
__all__ = [
    "install_screw_symmetry",
    "install_screw_frames",
    "install_emergent_screw_patch",
    "screw_frames",
    "close_packed_geometry",
    "groove_offsets",
    "n_for_full_coordination",
]


def install_screw_symmetry(
    subunits_per_turn,
    n_subunits,
    *,
    mode="emergent",
    rise=None,
    r_target=None,
    subunit_size=None,
    radius_bias=0.3,
    contact_dist=4.0,
    axis=(0, 0, 1),
):
    """Build screw frames and patch RFD3 in one call.

    Returns ``(sym_id, info)`` where ``sym_id`` (= ``f"C{n_subunits}"``) is what
    you pass to rfd3 as ``symmetry.id``.

    Parameters
    ----------
    subunits_per_turn : float
        Sets twist = 360 / this. Half-integer (N.5) -> staggered groove.
    n_subunits : int
        Total chains. Use >= ``n_for_full_coordination(subunits_per_turn)``.
    mode : {'emergent','closepack','contact'}
        emergent  - rotate ASU in place + axial rise; radius emergent (or soft r_target).
        closepack - impose analytic (R, rise) from `subunit_size` so the groove closes.
        contact   - fold-aware feedback controller (forces contact along true offsets).
    rise : float, optional
        Axial rise per subunit (Å). Required unless mode='closepack'.
    r_target : float, optional
        Soft target for the screw radius (Å). Controls lumen / hollow-vs-solid.
    subunit_size : float, optional
        Effective subunit diameter (Å); required for mode='closepack'.
    """
    if mode == "closepack":
        if subunit_size is None:
            raise ValueError("mode='closepack' requires subunit_size (Å).")
        R, rise = close_packed_geometry(subunits_per_turn, subunit_size)
        r_target = R
    if rise is None:
        raise ValueError("rise is required (or use mode='closepack' with subunit_size).")

    frames = screw_frames(subunits_per_turn, n_subunits, rise, axis)
    install_screw_frames(n=n_subunits, helical_frames=frames)
    install_emergent_screw_patch(
        frames,
        r_target=r_target,
        radius_bias=radius_bias,
        contact_mode=(mode == "contact"),
        subunits_per_turn=subunits_per_turn,
        contact_dist=contact_dist,
    )
    return f"C{n_subunits}", {
        "mode": mode,
        "twist_deg": 360.0 / subunits_per_turn,
        "rise": rise,
        "r_target": r_target,
        "n_subunits": n_subunits,
    }
