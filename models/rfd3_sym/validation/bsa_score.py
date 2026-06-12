"""Inter-subunit buried surface area (BSA) for an assembly — a real interface
metric (not just proximity). BSA = Σ_chains SASA(chain alone) − SASA(assembly),
summed over atoms (counts both faces of each interface). Usage:

    python bsa_score.py <structure.pdb>
"""
import sys
import numpy as np
import biotite.structure as struc
import biotite.structure.io.pdb as pdb


def main():
    arr = pdb.PDBFile.read(sys.argv[1]).get_structure(model=1)
    arr = arr[struc.filter_amino_acids(arr)]
    sasa_full = np.nansum(struc.sasa(arr, vdw_radii="Single"))
    chains = np.unique(arr.chain_id)
    sasa_iso = 0.0
    for c in chains:
        sasa_iso += np.nansum(struc.sasa(arr[arr.chain_id == c], vdw_radii="Single"))
    bsa = sasa_iso - sasa_full
    print(f"{bsa:.0f} {bsa/len(chains):.0f}")  # total BSA, per-subunit BSA


if __name__ == "__main__":
    main()
