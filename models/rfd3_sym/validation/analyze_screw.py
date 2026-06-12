"""Analyze an emergent-radius RFD3 screw output: recover (twist, rise),
report the model's EMERGENT radius, and classify all-atom inter-subunit
contacts (detached / interface / clash). Usage:

    python analyze_screw.py <cif.gz> --twist <deg> --rise <A> [--label X]
"""
import argparse, gzip, tempfile, itertools, json
import gemmi, numpy as np


def load(path):
    with tempfile.NamedTemporaryFile("w", suffix=".cif", delete=False) as t:
        t.write(gzip.open(path, "rt").read()); tmp = t.name
    m = gemmi.read_structure(tmp)[0]
    ca, hv = {}, {}
    for ch in m:
        ca[ch.name] = np.array([[a.pos.x, a.pos.y, a.pos.z] for r in ch for a in r if a.name == "CA"])
        hv[ch.name] = np.array([[a.pos.x, a.pos.y, a.pos.z] for r in ch for a in r if a.element.name != "H"])
    return ca, hv


def kabsch(P, Q):
    Pc, Qc = P.mean(0), Q.mean(0); H = (P - Pc).T @ (Q - Qc)
    U, _, Vt = np.linalg.svd(H); d = np.sign(np.linalg.det(Vt.T @ U.T))
    R = Vt.T @ np.diag([1, 1, d]) @ U.T
    return R, Qc - R @ Pc


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("cif"); ap.add_argument("--twist", type=float, required=True)
    ap.add_argument("--rise", type=float, required=True); ap.add_argument("--label", default="")
    a = ap.parse_args()
    ca, hv = load(a.cif); ids = list(ca); n = len(ids); axis = np.array([0, 0, 1.])

    tw, ri = [], []
    for x, y in zip(ids[:-1], ids[1:]):
        R, t = kabsch(ca[x], ca[y])
        tw.append(np.degrees(np.arccos(np.clip((np.trace(R) - 1) / 2, -1, 1)))); ri.append(float(t @ axis))
    radii = [np.linalg.norm(ca[i].mean(0)[:2]) for i in ids]

    D = np.full((n, n), 1e9)
    for i, j in itertools.combinations(range(n), 2):
        D[i, j] = D[j, i] = np.sqrt(((hv[ids[i]][:, None] - hv[ids[j]][None]) ** 2).sum(-1)).min()
    det = sum(D[i, j] > 5 for i, j in itertools.combinations(range(n), 2))
    ifc = sum(2 <= D[i, j] <= 5 for i, j in itertools.combinations(range(n), 2))
    clash = sum(D[i, j] < 2 for i, j in itertools.combinations(range(n), 2))
    nn = [D[i][np.arange(n) != i].min() for i in range(n)]

    r = dict(label=a.label, n_chains=n, twist_recovered=round(float(np.mean(tw)), 2),
             twist_asked=a.twist, rise_recovered=round(float(np.mean(ri)), 2), rise_asked=a.rise,
             emergent_radius=round(float(np.mean(radii)), 1),
             nn_gap_min=round(float(min(nn)), 1), nn_gap_med=round(float(np.median(nn)), 1),
             pairs_detached=int(det), pairs_interface=int(ifc), pairs_clash=int(clash))
    print(json.dumps(r))


if __name__ == "__main__":
    main()
