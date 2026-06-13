"""One-line fiber scorecard: is it BOTH fully-coordinated (groove complete)
AND all-interfaces SS-aligned AND clash-free? For half-integer screw fibers
the groove directions are n±1 and n±round(t) and n±(round(t)+1).
Usage:  python scorecard.py <fiber.pdb> <subunits_per_turn>
"""
import sys, numpy as np
import biotite.structure as struc
import biotite.structure.io.pdb as pdb

spt = float(sys.argv[2]); k = int(round(spt))
need = {1, k, k + 1}                      # groove offsets a central subunit should contact
cut, atol = 8.0, 40.0

arr = pdb.PDBFile.read(sys.argv[1]).get_structure(model=1)
arr = arr[struc.filter_amino_acids(arr)]
chains = list(dict.fromkeys(arr.chain_id)); n = len(chains)
ca, sse = {}, {}
for ch in chains:
    sub = arr[arr.chain_id == ch]
    ca[ch] = sub[sub.atom_name == "CA"].coord
    s = struc.annotate_sse(sub)
    sse[ch] = np.array(list(s)[:len(ca[ch])] + ["c"] * max(0, len(ca[ch]) - len(s)))
hv = {ch: arr[(arr.chain_id == ch)].coord for ch in chains}

c = n // 2; cc = chains[c]
def ax(p):
    p = p - p.mean(0); return np.linalg.svd(p, full_matrices=False)[2][0]

present, aligned_all, clash = set(), True, 0
for j, cj in enumerate(chains):
    if j == c: continue
    D = np.linalg.norm(ca[cc][:, None] - ca[cj][None], axis=-1)
    # NOTE: inter-subunit heavy-atom overlap. 2.0 A badly under-counts residue-level
    # clashes (a 451-RFD3-clash structure can have ~4 pairs <2 A). Use 2.7 A as a
    # proxy, but RFD3's own n_clashing.* metric is authoritative — always cross-check.
    hvD = np.linalg.norm(hv[cc][:, None] - hv[cj][None], axis=-1).min()
    if hvD < 2.7: clash += 1
    if D.min() >= cut: continue
    o = abs(j - c); present.add(o)
    ci = np.where(D.min(1) < cut)[0]; ni = np.where(D.min(0) < cut)[0]
    h1 = (sse[cc][ci] == "a").mean(); h2 = (sse[cj][ni] == "a").mean()
    e1 = (sse[cc][ci] == "b").mean(); e2 = (sse[cj][ni] == "b").mean()
    ang = np.degrees(np.arccos(np.clip(abs(np.dot(ax(ca[cc][ci]), ax(ca[cj][ni]))), 0, 1)))
    al = (h1 > .5 and h2 > .5 and ang < atol) or (e1 > .5 and e2 > .5 and ang < atol)
    if o in need:
        aligned_all &= al

groove = need.issubset(present)
both = groove and aligned_all and clash == 0
print(f"{sys.argv[1].split('/')[-1]:30s} groove={'Y' if groove else 'N'}({sorted(present & need)}) "
      f"all_aligned={'Y' if aligned_all else 'N'} clash<2={clash}  -> BOTH={'*** YES ***' if both else 'no'}")
sys.exit(0 if both else 1)
