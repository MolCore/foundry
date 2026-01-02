#!/usr/bin/env python3
"""
Sync helper for Foundry database mirrors on the databases server.

This script is designed to populate:
  - /runtime/databases/foundry/ccd  (AtomWorks CCD mirror layout)
  - /runtime/databases/foundry/pdb  (recommended wwPDB/rcsb divided mmCIF layout)

It is safe to re-run; it will skip files that are already present.

Notes
-----
1) CCD layout expected by AtomWorks:
     CCD_MIRROR_PATH/<first_letter>/<CODE>/<CODE>.cif

2) PyRosetta is unrelated to this; CCD/PDB mirrors are for AtomWorks/Foundry I/O.
"""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path


DEFAULT_ROOT = Path("/runtime/databases/foundry")

# These rsync modules are commonly available; choose one that works on your network.
CCD_RSYNC_SOURCES = [
    "rsync.wwpdb.org::ftp/pub/pdb/data/monomers/",
    "rsync.rcsb.org::ftp/pdb/data/monomers/",
]
PDB_RSYNC_SOURCES = [
    "rsync.wwpdb.org::ftp/pub/pdb/data/structures/divided/mmCIF/",
    "rsync.rcsb.org::ftp/pdb/data/structures/divided/mmCIF/",
]


@dataclass(frozen=True)
class Paths:
    root: Path

    @property
    def ccd_root(self) -> Path:
        return self.root / "ccd"

    @property
    def pdb_root(self) -> Path:
        return self.root / "pdb"

    @property
    def staging(self) -> Path:
        return self.root / "_staging"

    @property
    def ccd_staging(self) -> Path:
        # raw rsync pulls monomers into e.g. a/ATP.cif, b/BLA.cif, ...
        return self.staging / "ccd_monomers_raw"

    @property
    def pdb_staging(self) -> Path:
        return self.staging / "pdb_mmcif_divided_raw"


def _run(cmd: list[str]) -> None:
    print("+", " ".join(cmd))
    subprocess.run(cmd, check=True)


def ensure_dirs(paths: Paths) -> None:
    paths.root.mkdir(parents=True, exist_ok=True)
    paths.staging.mkdir(parents=True, exist_ok=True)
    paths.ccd_root.mkdir(parents=True, exist_ok=True)
    paths.pdb_root.mkdir(parents=True, exist_ok=True)


def _pick_rsync_source(candidates: list[str]) -> str:
    """
    Pick the first reachable rsync source by attempting a quick list.
    """
    for src in candidates:
        try:
            subprocess.run(["rsync", "--list-only", src], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            return src
        except Exception:
            continue
    raise RuntimeError(
        "No rsync source was reachable. Tried:\n  - " + "\n  - ".join(candidates)
    )


def rsync_tree(src: str, dest: Path, *, delete: bool = False) -> None:
    """
    Mirror a remote rsync tree into dest.
    """
    dest.mkdir(parents=True, exist_ok=True)
    cmd = ["rsync", "-rtv", "--info=progress2"]
    if delete:
        cmd.append("--delete")
    cmd += [src, f"{dest}/"]
    _run(cmd)


def repack_ccd_monomers_to_atomworks_layout(ccd_raw_root: Path, ccd_dest_root: Path) -> tuple[int, int]:
    """
    Convert the wwPDB/rcsb monomer layout (usually <letter>/<CODE>.cif)
    into AtomWorks layout: <LETTER>/<CODE>/<CODE>.cif

    Returns: (n_copied, n_skipped)
    """
    n_copied = 0
    n_skipped = 0

    for cif_path in ccd_raw_root.rglob("*.cif"):
        # Expect leaf like ".../a/ATP.cif" but keep it generic.
        code = cif_path.stem.upper()
        if not code:
            continue
        first = code[0]

        out_dir = ccd_dest_root / first / code
        out_file = out_dir / f"{code}.cif"
        out_dir.mkdir(parents=True, exist_ok=True)

        if out_file.exists() and out_file.stat().st_size > 0:
            n_skipped += 1
            continue

        shutil.copy2(cif_path, out_file)
        n_copied += 1

    # Touch a cache file for AtomWorks scanning speed (optional)
    cache_file = ccd_dest_root / ".ccd_codes_cache"
    try:
        codes = sorted({p.parent.name for p in ccd_dest_root.glob("*/*/*.cif")})
        cache_file.write_text("\n".join(codes) + "\n")
    except Exception:
        pass

    return n_copied, n_skipped


def cmd_init(args: argparse.Namespace) -> None:
    paths = Paths(Path(args.root))
    ensure_dirs(paths)
    print(f"OK: initialized {paths.root}")


def cmd_sync_ccd(args: argparse.Namespace) -> None:
    paths = Paths(Path(args.root))
    ensure_dirs(paths)

    src = args.source or _pick_rsync_source(CCD_RSYNC_SOURCES)
    print(f"Using CCD rsync source: {src}")

    rsync_tree(src, paths.ccd_staging, delete=args.delete)

    copied, skipped = repack_ccd_monomers_to_atomworks_layout(paths.ccd_staging, paths.ccd_root)
    print(f"CCD repack complete: copied={copied}, skipped={skipped}, dest={paths.ccd_root}")


def cmd_sync_pdb(args: argparse.Namespace) -> None:
    paths = Paths(Path(args.root))
    ensure_dirs(paths)

    src = args.source or _pick_rsync_source(PDB_RSYNC_SOURCES)
    print(f"Using PDB mmCIF rsync source: {src}")

    # Mirror into the canonical tree under pdb/data/structures/divided/mmCIF/...
    dest = paths.pdb_root / "data" / "structures" / "divided" / "mmCIF"
    rsync_tree(src, dest, delete=args.delete)
    print(f"PDB mirror complete: dest={dest}")


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--root", default=str(DEFAULT_ROOT), help="Root directory (default: /runtime/databases/foundry)")

    sub = p.add_subparsers(dest="cmd", required=True)

    p_init = sub.add_parser("init", help="Create directory skeleton under --root")
    p_init.set_defaults(func=cmd_init)

    p_ccd = sub.add_parser("sync-ccd", help="Rsync CCD monomers then repack into AtomWorks CCD layout")
    p_ccd.add_argument("--source", default=None, help="Override rsync source module")
    p_ccd.add_argument("--delete", action="store_true", help="Pass --delete to rsync (dangerous)")
    p_ccd.set_defaults(func=cmd_sync_ccd)

    p_pdb = sub.add_parser("sync-pdb", help="Rsync PDB divided mmCIF mirror into pdb/ tree")
    p_pdb.add_argument("--source", default=None, help="Override rsync source module")
    p_pdb.add_argument("--delete", action="store_true", help="Pass --delete to rsync (dangerous)")
    p_pdb.set_defaults(func=cmd_sync_pdb)

    args = p.parse_args()
    args.func(args)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


