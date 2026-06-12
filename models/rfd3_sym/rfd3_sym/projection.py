"""Emergent / radius-targeted / CONTACT-forced SCREW projection for RFD3.

Modes (set at install):
  - emergent           : subunit_i = asu @ R(i·twist) + i·rise·ẑ  (radius free)
  - r_target=R         : soft radial spring toward R (controls lumen/topology)
  - contact_mode=True  : FOLD-AWARE contact controller (screw-specific). Forces
                         BOTH the lateral and the turn-to-turn interfaces a
                         continuous fibre needs, for ANY subunits/turn incl.
                         fractional folds.

Fold-aware contact controller (contact_mode):
  Integer folds have their contacting neighbours at offsets i±1 (lateral) and
  i±spt (turn-to-turn). Fractional folds do NOT — a 7/2 helix (3.5/turn) packs
  along offsets {1,3}, a 31/5 (6.2/turn) along {1,6}, etc. So instead of
  ASSUMING the offsets, each projection step we MEASURE the ASU's gap to every
  other subunit, classify each neighbour as lateral (|wrapped angle| ≥ 45°,
  governed by radius R) or axial (< 45°, governed by rise d), and drive the
  nearest gap in each class toward a contact target — with a clash floor that
  pushes apart if anything gets too close. R and d are state, refined over the
  trajectory (seeded from the analytic close-packed estimate). This is the
  available way to force contact in RFD3's no-grad sampler.
"""

from __future__ import annotations
import numpy as np

_ORIGINAL = None
_FRAMES = None
_R_TARGET = None
_RADIUS_BIAS = 0.3
_CONTACT = False
_SPT = None
_CONTACT_DIST = 4.0      # target inter-subunit min all-atom gap (Å) for contact
_CLASH_FLOOR = 2.6       # below this = clash -> push apart
_GAIN = 0.35
_EMA = 0.3
_state = {"R": None, "d": None}


def install_emergent_screw_patch(frames, r_target=None, radius_bias=0.3,
                                 contact_mode=False, subunits_per_turn=None,
                                 lateral_overlap=0.9, axial_overlap=0.9,
                                 contact_dist=4.0):
    import torch
    from rfd3.inference.symmetry import symmetry_utils as _su
    from rfd3.inference.symmetry.atom_array import FIXED_ENTITY_ID, FIXED_TRANSFORM_ID

    global _ORIGINAL, _FRAMES, _R_TARGET, _RADIUS_BIAS, _CONTACT, _SPT, _CONTACT_DIST, _state
    if not getattr(_su, "_emergent_screw_patch_installed", False):
        _ORIGINAL = _su.apply_symmetry_to_xyz_atomwise
    _FRAMES = {i: (torch.as_tensor(np.asarray(R), dtype=torch.float32),
                   torch.as_tensor(np.asarray(t), dtype=torch.float32))
               for i, (R, t) in enumerate(frames)}
    _R_TARGET = None if r_target is None else float(r_target)
    _RADIUS_BIAS = float(radius_bias)
    _CONTACT = bool(contact_mode)
    _SPT = None if subunits_per_turn is None else float(subunits_per_turn)
    _CONTACT_DIST = float(contact_dist)
    _state = {"R": None, "d": None}
    # seed lateral/axial overlap into the analytic initial guess
    _ANALYTIC = {"alpha": float(lateral_overlap), "beta": float(axial_overlap)}
    if _CONTACT:
        assert _SPT is not None, "contact_mode needs subunits_per_turn"

    tw = None if _SPT is None else 2 * np.pi / _SPT

    def wrap_deg(a):
        return (a + 180.0) % 360.0 - 180.0

    def emergent_screw(X_L, sym_feats, partial_diffusion=False):
        eid = sym_feats["sym_entity_id"]; tid = sym_feats["sym_transform_id"]
        is_asu = sym_feats["is_sym_asu"]; fixed = eid == FIXED_ENTITY_ID
        if not partial_diffusion:
            X_L[:, ~fixed, :] = X_L[:, ~fixed, :] - X_L[:, ~fixed, :].mean(dim=1, keepdim=True)
        out = X_L.clone()
        for e in torch.unique(eid):
            if int(e) == FIXED_ENTITY_ID:
                continue
            em = eid == e
            am = is_asu & em
            if am.sum() == 0:
                continue
            asu = X_L[:, am, :]                              # (B,La,3)
            com = asu.mean(dim=1, keepdim=True)
            cxy = com.clone(); cxy[..., 2] = 0.0
            r = torch.linalg.norm(cxy, dim=-1, keepdim=True)
            direction = cxy / (r + 1e-6)
            fb = torch.zeros_like(cxy); fb[..., 0] = 1.0
            direction = torch.where(r < 1e-3, fb, direction)

            rise_override = None
            if _CONTACT:
                rel = asu - com
                tang = torch.zeros_like(direction)
                tang[..., 0] = -direction[..., 1]; tang[..., 1] = direction[..., 0]
                w_ext = float((rel * tang).sum(-1).max() - (rel * tang).sum(-1).min())
                h_ext = float(asu[..., 2].max() - asu[..., 2].min())
                if _state["R"] is None:   # analytic close-packed seed
                    _state["R"] = _ANALYTIC["alpha"] * w_ext / (2 * np.sin(np.pi / _SPT))
                    _state["d"] = _ANALYTIC["beta"] * h_ext / _SPT
                R = max(4.0, min(70.0, _state["R"]))
                d = max(2.0, min(30.0, _state["d"]))
                asu = asu + (direction * R - cxy)            # place ASU at radius R
                rise_override = d

            elif _R_TARGET is not None:
                asu = asu + _RADIUS_BIAS * (direction * _R_TARGET - cxy)

            asu_atoms = None
            sub_atoms = {}
            for i in torch.unique(tid[em]).tolist():
                if int(i) == FIXED_TRANSFORM_ID or int(i) not in _FRAMES:
                    continue
                sub = em & (tid == i)
                R_, t = _FRAMES[int(i)]
                R_ = R_.to(asu.device, dtype=asu.dtype)
                if rise_override is not None:
                    t = torch.tensor([0.0, 0.0, int(i) * rise_override], device=asu.device, dtype=asu.dtype)
                else:
                    t = t.to(asu.device, dtype=asu.dtype)
                built = torch.einsum("blc,cd->bld", asu, R_) + t
                out[:, sub, :] = built
                if _CONTACT:
                    sub_atoms[int(i)] = built[0]               # (Lk,3)  B=1
                    if bool(is_asu[sub][0]):
                        asu_atoms = built[0]

            # ---- fold-aware feedback update of (R, d) from measured gaps ----
            if _CONTACT and asu_atoms is not None and len(sub_atoms) > 1:
                asu_tid = int(tid[am][0])
                g_lat = []; g_ax = []
                for k, atoms in sub_atoms.items():
                    if k == asu_tid:
                        continue
                    gap = float(torch.cdist(asu_atoms, atoms).min())
                    ang = abs(wrap_deg((k - asu_tid) * np.degrees(tw)))
                    (g_lat if ang >= 45.0 else g_ax).append(gap)
                R, d = _state["R"], _state["d"]
                if g_lat:
                    gl = min(g_lat)
                    R = R + (_GAIN * 3.0 if gl < _CLASH_FLOOR else -_GAIN * (gl - _CONTACT_DIST))
                if g_ax:
                    ga = min(g_ax)
                    d = d + (_GAIN * 3.0 if ga < _CLASH_FLOOR else -_GAIN * (ga - _CONTACT_DIST))
                _state["R"] = (1 - _EMA) * _state["R"] + _EMA * max(4.0, min(70.0, R))
                _state["d"] = (1 - _EMA) * _state["d"] + _EMA * max(2.0, min(30.0, d))
        return out

    _su.apply_symmetry_to_xyz_atomwise = emergent_screw
    _su._emergent_screw_patch_installed = True
    mode = (f"FOLD-AWARE contact (spt={_SPT}, target={_CONTACT_DIST}Å, clash_floor={_CLASH_FLOOR}Å)"
            if _CONTACT else (f"soft R_target={_R_TARGET}" if _R_TARGET else "emergent"))
    print(f"[prism_helical_emergent_patch] installed — {len(_FRAMES)} frames, radius: {mode}")


def uninstall():
    global _ORIGINAL, _FRAMES, _R_TARGET, _CONTACT
    if _ORIGINAL is None:
        return
    from rfd3.inference.symmetry import symmetry_utils as _su
    _su.apply_symmetry_to_xyz_atomwise = _ORIGINAL
    _su._emergent_screw_patch_installed = False
    _ORIGINAL = None; _FRAMES = None; _R_TARGET = None; _CONTACT = False
