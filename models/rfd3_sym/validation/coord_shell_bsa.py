"""Repeating growth-interface metric for a continuous screw fiber.
For a CENTRAL (fully-coordinated) subunit, report its total buried surface
area against its whole coordination shell (all other subunits), broken down
by |i-j| offset. This is the polymerization-relevant interface, not pairwise
dimers. Usage:  python coord_shell_bsa.py <fiber.pdb>
"""
import sys, numpy as np, biotite.structure as struc, biotite.structure.io.pdb as pdb

arr = pdb.PDBFile.read(sys.argv[1]).get_structure(model=1)
arr = arr[struc.filter_amino_acids(arr)]
chains = list(dict.fromkeys(arr.chain_id)); n = len(chains)
c = n // 2                                   # central subunit
sasa_iso = {ch: np.nansum(struc.sasa(arr[arr.chain_id == ch], vdw_radii="Single")) for ch in chains}
cc = chains[c]
per_off, total = {}, 0.0
for j, cj in enumerate(chains):
    if j == c:
        continue
    pair = arr[(arr.chain_id == cc) | (arr.chain_id == cj)]
    bsa = sasa_iso[cc] + sasa_iso[cj] - np.nansum(struc.sasa(pair, vdw_radii="Single"))
    if bsa > 30:
        per_off[abs(j - c)] = per_off.get(abs(j - c), 0.0) + bsa
        total += bsa
print(f"central subunit {cc} ({n} chains): coordination-shell BSA = {total:.0f} Å²")
for o in sorted(per_off):
    print(f"   offset n±{o}: {per_off[o]:.0f} Å²")
