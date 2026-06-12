"""Per-interface secondary-structure ALIGNMENT check for a screw fiber.
For the central (fully-coordinated) subunit, examine each contacting neighbour
(by |i-j| offset) and decide whether that interface is SS-aligned:
both faces structured (helix or sheet) of the SAME type, and their interface
patches roughly parallel/antiparallel (principal-axis angle small).

Reports per offset, and whether ALL interfaces are aligned. Usage:
    python interface_ss.py <fiber.pdb> [contact_cutoff=8] [axis_tol_deg=40]
"""
import sys, numpy as np
import biotite.structure as struc
import biotite.structure.io.pdb as pdb

cut = float(sys.argv[2]) if len(sys.argv) > 2 else 8.0
atol = float(sys.argv[3]) if len(sys.argv) > 3 else 40.0

arr = pdb.PDBFile.read(sys.argv[1]).get_structure(model=1)
arr = arr[struc.filter_amino_acids(arr)]
chains = list(dict.fromkeys(arr.chain_id)); n = len(chains)
ca, sse = {}, {}
for ch in chains:
    sub = arr[arr.chain_id == ch]
    ca[ch] = sub[sub.atom_name == "CA"].coord
    s = struc.annotate_sse(sub)                 # 'a' helix, 'b' sheet, 'c' coil
    if len(s) != len(ca[ch]):                   # guard length mismatch
        s = np.array(list(s)[:len(ca[ch])] + ["c"] * max(0, len(ca[ch]) - len(s)))
    sse[ch] = s

def axis(coords):
    c = coords - coords.mean(0)
    return np.linalg.svd(c, full_matrices=False)[2][0]

def frac(ss):  # (%helix, %sheet) of a residue-SS array
    if len(ss) == 0: return 0.0, 0.0
    return float((ss == "a").mean()), float((ss == "b").mean())

c = n // 2; cc = chains[c]
print(f"central subunit {cc} ({n} chains), contact cutoff {cut} Å, axis tol {atol}°")
all_aligned, n_iface = True, 0
for j, cj in enumerate(chains):
    if j == c: continue
    D = np.linalg.norm(ca[cc][:, None, :] - ca[cj][None, :, :], axis=-1)
    if D.min() >= cut: continue
    n_iface += 1
    ci = np.where(D.min(1) < cut)[0]; ni = np.where(D.min(0) < cut)[0]
    ch_h, ch_s = frac(sse[cc][ci]); nh, ns = frac(sse[cj][ni])
    ang = np.degrees(np.arccos(np.clip(abs(np.dot(axis(ca[cc][ci]), axis(ca[cj][ni]))), 0, 1)))
    helix_al = ch_h > 0.5 and nh > 0.5 and ang < atol
    sheet_al = ch_s > 0.5 and ns > 0.5 and ang < atol
    aligned = helix_al or sheet_al
    all_aligned &= aligned
    kind = "HELIX-aligned" if helix_al else ("SHEET-aligned" if sheet_al else "NOT aligned")
    print(f"  offset n±{abs(j-c):<2}: central H{ch_h*100:3.0f}%/E{ch_s*100:3.0f}%  "
          f"neigh H{nh*100:3.0f}%/E{ns*100:3.0f}%  axis {ang:4.0f}°  -> {kind}")
print(f"\n  {n_iface} interfaces; ALL ALIGNED: {'YES' if all_aligned and n_iface>0 else 'NO'}")
sys.exit(0 if (all_aligned and n_iface > 0) else 1)
