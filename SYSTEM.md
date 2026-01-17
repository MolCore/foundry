# Cross-platform collaboration notes (macOS + Linux)

This repo is used from multiple machines (e.g. macOS laptop + Linux servers). To keep branches mergeable:

## Rules of thumb
- **Keep tracked config portable**: anything committed to git should work (or fail loudly) on both macOS and Linux.
- **Put machine-specific paths in gitignored files** (never commit absolute host paths).

## direnv layout
- `.envrc` (tracked): activates the repo-local venv (`./.venv`) and then sources `.envrc.local` if present.
- `.envrc.local` (gitignored): your machine-specific overrides (paths, mirrors).
- `.envrc.local.example` (tracked): template you can copy.

### Setup steps (both platforms)
1. Create the repo venv:

```bash
uv python install 3.12
uv venv --python 3.12
uv pip install -e ".[all,dev]"
```

2. Enable direnv (one-time per machine) and allow the repo:

```bash
direnv allow
```

3. Create local overrides:

```bash
cp .envrc.local.example .envrc.local
${EDITOR:-vi} .envrc.local
direnv reload
```

## Mirrors (AtomWorks)
AtomWorks reads:
- `CCD_MIRROR_PATH`
- `PDB_MIRROR_PATH`

Recommended conventions:
- **Databases server**: `/runtime/databases/foundry/{ccd,pdb}`
- **Workstation**: a mounted mirror under `$HOME/mounts/...` or repo-local `.foundry_mirrors/`

### Platform-specific paths belong in `.envrc.local`
Examples (choose one and put it in `.envrc.local`):
- **Linux server**: `/runtime/databases/foundry/{ccd,pdb}`
- **macOS workstation (Ariel)**: `$HOME/mounts/runtime/databases/foundry/{ccd,pdb}`
- **other workstation layout**: `$HOME/mounts/foundry_databases/{ccd,pdb}`

This keeps the repo portable while still supporting per-machine configuration.

## Prompt customization (optional, machine-local)
If you want your shell prompt to show a consistent label like `(u-foundry)` while inside this repo,
set it in `.envrc.local`. Prompt theming is shell/user specific, so it should **not** be committed.

## What should be gitignored
- `.envrc.local`
- `.foundry_mirrors/`
- any machine-local datasets, caches, and outputs


