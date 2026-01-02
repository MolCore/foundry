# Foundry databases on the server (`/runtime/databases/foundry`)

Foundry/AtomWorks can use local on-disk mirrors for:

- **CCD** (Chemical Component Dictionary): `CCD_MIRROR_PATH`
- **PDB** (structures): `PDB_MIRROR_PATH`

On this server, we standardize on:

- `CCD_MIRROR_PATH=/runtime/databases/foundry/ccd`
- `PDB_MIRROR_PATH=/runtime/databases/foundry/pdb`

The repo-local `.envrc` is configured to **prefer** these paths when they exist.

## Expected directory layout

### CCD layout (required by AtomWorks)

AtomWorks expects per-component CIFs in this layout:

```
/runtime/databases/foundry/ccd/
  A/ALA/ALA.cif
  H/HEM/HEM.cif
  ...
```

This matches AtomWorks’ `_get_ccd_path()` logic (first-letter directory, then component code directory).

### PDB layout (recommended)

For full PDB mirrors, we recommend storing the official divided mmCIF tree under:

```
/runtime/databases/foundry/pdb/
  data/structures/divided/mmCIF/ab/1abc.cif.gz
  ...
```

This is the standard wwPDB/rcsb distribution layout and is convenient for rsync mirroring.

## Scripts

Use `tools/databases/sync_foundry_databases.py` to **initialize** directories and (optionally) sync:

- CCD monomers from wwPDB/rcsb rsync, then **repack** them into AtomWorks’ expected CCD layout.
- PDB divided mmCIF mirror into the recommended layout.

The script is resumable and safe to re-run.


