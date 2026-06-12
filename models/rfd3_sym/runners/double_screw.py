"""Extend a screw assembly to 2x length: duplicate it and move the copy one
whole-assembly step along the screw (apply S^n, where S is the per-subunit
screw operator recovered from the structure). Output: a 2n-chain PDB that
continues the helix seamlessly across the junction.

Usage:  python double_screw.py <in.pdb> <out_doubled.pdb>
"""
import sys
import numpy as np

ALPHA = list("ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789")


def kabsch(P, Q):
    Pc, Qc = P.mean(0), Q.mean(0)
    H = (P - Pc).T @ (Q - Qc)
    U, _, Vt = np.linalg.svd(H)
    d = np.sign(np.linalg.det(Vt.T @ U.T))
    R = Vt.T @ np.diag([1, 1, d]) @ U.T
    return R, Qc - R @ Pc


def main():
    src, out = sys.argv[1], sys.argv[2]
    lines = [l for l in open(src) if l.startswith(("ATOM", "HETATM"))]
    # group by chain (in order of appearance); collect CA coords per chain
    order, ca = [], {}
    for l in lines:
        ch = l[21]
        if ch not in ca:
            ca[ch] = []; order.append(ch)
        if l[12:16].strip() == "CA":
            ca[ch].append([float(l[30:38]), float(l[38:46]), float(l[46:54])])
    n = len(order)
    assert 2 * n <= len(ALPHA), f"{2*n} chains exceeds single-char chain IDs"
    C0, C1 = np.array(ca[order[0]]), np.array(ca[order[1]])
    R_s, t_s = kabsch(C0, C1)                       # per-subunit screw operator
    # S^n : R_n = R_s^n ;  t_n = sum_{k=0}^{n-1} R_s^k t_s
    R_n = np.linalg.matrix_power(R_s, n)
    t_n = np.zeros(3); Rk = np.eye(3)
    for _ in range(n):
        t_n += Rk @ t_s; Rk = R_s @ Rk
    cmap = {c: ALPHA[i] for i, c in enumerate(order)}        # seg1 chain ids
    cmap2 = {c: ALPHA[n + i] for i, c in enumerate(order)}   # seg2 chain ids

    def emit(l, chain_id, xyz=None):
        if xyz is None:
            return l[:21] + chain_id + l[22:]
        x, y, z = xyz
        return l[:21] + chain_id + l[22:30] + f"{x:8.3f}{y:8.3f}{z:8.3f}" + l[54:]

    with open(out, "w") as f:
        for l in lines:                              # segment 1 (unchanged geom)
            f.write(emit(l, cmap[l[21]]))
        f.write("TER\n")
        for l in lines:                              # segment 2 = S^n · segment 1
            p = np.array([float(l[30:38]), float(l[38:46]), float(l[46:54])])
            q = R_n @ p + t_n
            f.write(emit(l, cmap2[l[21]], q))
        f.write("END\n")
    rise = float(t_s @ np.array([0, 0, 1.0]))
    print(f"doubled {n}->{2*n} chains; per-subunit rise {rise:.2f} Å, wrote {out}")


if __name__ == "__main__":
    main()
