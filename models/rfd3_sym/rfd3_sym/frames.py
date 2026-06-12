"""Runtime patch: helical-via-Cn — hide helical frames behind a Cn symmetry id.

The trick (from the ML-architecture review + user insight):

    - Tell RFD3 `symmetry.id = "C{n}"`  where n = n_units
    - Monkey-patch ``get_cyclic_frames(n)`` to return OUR helical (R, t) frames
      instead of the pure n-fold cyclic frames
    - Model sees C{n} in its conditioning features (in-distribution sym_id,
      d_chain_II pair bias)
    - Sampler's per-step symmetric projection uses our helical frames
    - Result: model produces a well-formed ASU "as if" C{n}; sampler enforces
      the true helical arrangement each step

This cleanly separates what the model *sees* (standard in-distribution Cn)
from what the sampler *enforces* (our helical frames). The training-
distribution concern evaporates because the sampler's projection dominates.

Usage:
    from prism_helical_via_cn_patch import install_helical_via_cn_patch
    install_helical_via_cn_patch(n=17, helical_frames=spec.generate_frames())
    # now run rfd3 with `symmetry.id = "C17"` and it uses our helical frames
"""

from __future__ import annotations

import numpy as np


_ORIGINAL_CYCLIC = None
_INSTALLED_N: int | None = None
_INSTALLED_FRAMES: list[tuple[np.ndarray, np.ndarray]] | None = None


def install_helical_via_cn_patch(
    n: int,
    helical_frames: list[tuple[np.ndarray, np.ndarray]],
) -> None:
    """Patch ``rfd3.inference.symmetry.frames.get_cyclic_frames(n)`` to return
    our helical frames.

    Parameters
    ----------
    n : int
        The integer matching both ``len(helical_frames)`` and the Cn label
        we'll give RFD3 in the JSON (``symmetry.id = "C{n}"``).
    helical_frames : list[(R, t)]
        The helical SE(3) frames we want the sampler to use. Must have
        length exactly ``n``.

    After calling, the JSON should read:
        "symmetry": {"id": f"C{n}", "is_symmetric_motif": true}
    """
    global _ORIGINAL_CYCLIC, _INSTALLED_N, _INSTALLED_FRAMES

    if len(helical_frames) != n:
        raise ValueError(
            f"helical_frames has length {len(helical_frames)}, "
            f"but the Cn label requires n={n}"
        )

    import rfd3.inference.symmetry.frames as rfd_frames

    # Store the original (first-install only).
    if _ORIGINAL_CYCLIC is None:
        _ORIGINAL_CYCLIC = rfd_frames.get_cyclic_frames

    # Convert (R, t) tuples to whatever format RFD3 expects.
    # Looking at the upstream get_cyclic_frames return shape: list of
    # (R, t) tuples where R is (3, 3) and t is (3,). Keep the same contract.
    frames_for_rfd3: list[tuple[np.ndarray, np.ndarray]] = []
    for R, t in helical_frames:
        frames_for_rfd3.append(
            (np.asarray(R, dtype=np.float64), np.asarray(t, dtype=np.float64))
        )
    _INSTALLED_N = n
    _INSTALLED_FRAMES = frames_for_rfd3

    def patched_cyclic(order):
        if order == _INSTALLED_N:
            return _INSTALLED_FRAMES
        return _ORIGINAL_CYCLIC(order)

    rfd_frames.get_cyclic_frames = patched_cyclic
    print(
        f"[prism_helical_via_cn_patch] installed — get_cyclic_frames({n}) "
        f"will return our {n} helical frames; other Cn calls delegate to "
        f"upstream"
    )


def uninstall() -> None:
    """Restore the original get_cyclic_frames function."""
    global _ORIGINAL_CYCLIC, _INSTALLED_N, _INSTALLED_FRAMES
    if _ORIGINAL_CYCLIC is None:
        return
    import rfd3.inference.symmetry.frames as rfd_frames
    rfd_frames.get_cyclic_frames = _ORIGINAL_CYCLIC
    _ORIGINAL_CYCLIC = None
    _INSTALLED_N = None
    _INSTALLED_FRAMES = None


if __name__ == "__main__":
    # Self-test: install, then check that get_cyclic_frames returns our frames
    import sys
    sys.path.insert(0, "/runtime/molcore_science/molcore-einstein/src")
    from molcore_einstein.symmetry_oracle.prism_helical import HelicalSpec

    spec = HelicalSpec(rise=1.408, twist_deg=22.04, radius=80.0, n_units=17)
    frames = spec.generate_frames()

    install_helical_via_cn_patch(n=17, helical_frames=frames)

    from rfd3.inference.symmetry.frames import get_cyclic_frames
    returned = get_cyclic_frames(17)
    assert len(returned) == 17
    print(f"  C17 returns {len(returned)} frames ✓")
    print(f"  frame 1: R trace = {np.trace(returned[1][0]):.4f} "
          f"(expected {np.trace(frames[1][0]):.4f})")
    # Call an untouched Cn — should delegate to upstream
    c3 = get_cyclic_frames(3)
    print(f"  C3 (untouched) returns {len(c3)} frames via upstream")
