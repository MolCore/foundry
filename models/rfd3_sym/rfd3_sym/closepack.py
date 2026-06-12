"""Screw-lattice geometry: axial-rise frame construction + analytic close-pack.

A screw is a rotation (twist = 360/subunits_per_turn) plus an axial translation
(rise). For a continuous fibre we want a *central* subunit to contact its whole
groove shell. For a half-integer subunits/turn (t = N.5) that shell is the
staggered groove: offsets {1, floor(t), floor(t)+1}. `close_packed_geometry`
returns the (R, rise) at which those neighbour COM distances are all ~ the
subunit size (i.e. all in contact).
"""
from __future__ import annotations
import numpy as np


def screw_frames(subunits_per_turn, n_subunits, rise, axis=(0, 0, 1)):
    """n SE(3) frames (R_i, t_i): rotation by i*twist about `axis`, plus an
    AXIAL translation i*rise*axis (no radial offset -> radius stays emergent)."""
    axis = np.asarray(axis, float); axis /= np.linalg.norm(axis)
    tw = 2 * np.pi / subunits_per_turn

    def rodrigues(a, th):
        c, s = np.cos(th), np.sin(th)
        K = np.array([[0, -a[2], a[1]], [a[2], 0, -a[0]], [-a[1], a[0], 0.0]])
        return np.eye(3) + s * K + (1 - c) * (K @ K)

    return [(rodrigues(axis, tw * i), (i * rise) * axis) for i in range(n_subunits)]


def groove_offsets(subunits_per_turn):
    """The contacting neighbour offsets for a central subunit: 1 (lateral) and
    the two turn neighbours floor(t), floor(t)+1 (the staggered groove)."""
    k = int(np.floor(subunits_per_turn))
    return [1, k, k + 1]


def close_packed_geometry(subunits_per_turn, subunit_size):
    """Analytic (R, rise) so all groove-neighbour COM distances ~= subunit_size.
    Minimises the spread of {d_1, d_k, d_{k+1}} (in units of R), then scales by
    subunit_size. Returns (R, rise)."""
    tw = np.radians(360.0 / subunits_per_turn)
    offs = groove_offsets(subunits_per_turn)

    def d_over_R(x, o):  # COM distance of offset o, divided by R, for rise/R = x
        return np.sqrt((2 * np.sin(o * tw / 2)) ** 2 + (o * x) ** 2)

    best = None
    for x in np.linspace(0.001, 0.6, 6000):
        v = np.array([d_over_R(x, o) for o in offs])
        spread = (v.max() - v.min()) / v.mean()
        if best is None or spread < best[0]:
            best = (spread, x, float(v.mean()))
    _, x, dmean = best
    R = subunit_size / dmean
    return R, x * R


def n_for_full_coordination(subunits_per_turn):
    """Minimum n_subunits for a central subunit to have its whole shell
    (one turn above and below + buffer): ceil(2*t) + 2."""
    return int(np.ceil(2 * subunits_per_turn)) + 2
