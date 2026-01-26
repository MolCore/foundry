# molecore_foundry Environment Specification

This directory defines a **portable uv environment specification** for foundry-based biomolecular modeling workflows.

## What This Is

A reusable Python environment package that includes:
- Core scientific computing stack (numpy, scipy, pandas)
- Biomolecular tooling (AtomWorks, Biotite)
- PyTorch (CPU by default, upgrade to CUDA on GPU platforms)
- Jupyter notebook support
- Optional extras for agentic workflows, Modal cloud, and more

This environment spec is designed to work across **macOS and Linux** platforms.

## Quick Install

```bash
# Install uv (if not already installed)
curl -LsSf https://astral.sh/uv/install.sh | sh

# Create environment using this spec
uv python install 3.12
uv venv ~/.venvs/molecore_foundry --python 3.12
source ~/.venvs/molecore_foundry/bin/activate

# Install the environment package
uv pip install -e /path/to/foundry/tools/envs/molecore_foundry
```

## What's Included

### Core Dependencies (Always Installed)
- **atomworks** - Unified biomolecular structure processing
- **biotite** - Computational biology toolkit
- **torch** - Machine learning (CPU by default)
- **numpy, scipy, pandas** - Scientific computing
- **jupyterlab, ipykernel** - Interactive notebooks
- **requests, httpx, pyyaml** - Utilities

See `pyproject.toml` for the complete dependency specification.

### Optional Extras

Install additional dependency groups as needed:

```bash
# AtomWorks ML capabilities (pulls additional ML deps)
uv pip install "molecore-foundry-env[atomworks_ml]"

# Agentic workflow tools (OpenAI, Anthropic, Groq SDKs)
uv pip install "molecore-foundry-env[agentic]"

# Modal cloud client
uv pip install "molecore-foundry-env[modal]"

# All optional extras
uv pip install "molecore-foundry-env[all]"
```

## Platform-Specific Setup

This environment spec is **platform-agnostic**. For platform-specific instructions (GPU setup, database mirrors, visualization tools), see:

- **[macOS Local Setup](../../docs/platforms/macos-local.md)** - Development with PyMOL, CPU-only
- **[Linux + NVIDIA Setup](../../docs/platforms/linux-nvidia.md)** - CUDA PyTorch, GPU compute
- **[Modal Cloud Setup](../../docs/platforms/modal-cloud.md)** - Serverless production pipelines

### Key Platform Differences

| Aspect | macOS | Linux GPU | Modal Cloud |
|--------|-------|-----------|-------------|
| PyTorch | CPU (default) | **Upgrade to CUDA** | Baked into image |
| PyMOL | Install via Homebrew | Not needed | Not needed |
| Databases | Mounted network paths | Direct filesystem | Volume or on-demand |

**GPU platforms:** After installing this environment, upgrade PyTorch to CUDA:
```bash
uv pip install --upgrade torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu124
```

## Using with Foundry

After setting up this environment, install Foundry itself:

### Option A: Editable Install (Development)
```bash
uv pip install -e "/path/to/foundry[all,dev]"
```

### Option B: Released Package
```bash
uv pip install "rc-foundry[all]"
```

## Machine-Specific Configuration

**Database mirrors, paths, and other machine-specific settings belong in `.envrc.local`**, not committed to git.

See [SYSTEM.md](../../SYSTEM.md) for the cross-platform coordination pattern using direnv.

Example `.envrc.local`:
```bash
# Linux GPU server
export CCD_MIRROR_PATH="/runtime/databases/foundry/ccd"
export PDB_MIRROR_PATH="/runtime/databases/foundry/pdb"

# macOS with mounted databases
export CCD_MIRROR_PATH="$HOME/mounts/runtime/databases/foundry/ccd"
export PDB_MIRROR_PATH="$HOME/mounts/runtime/databases/foundry/pdb"
```

## Package Maintenance

This is a **meta-package** - it doesn't contain code, just dependency specifications.

To update dependencies:
1. Edit `pyproject.toml`
2. Test on both macOS and Linux
3. Commit changes to the repository

The package is installed in **editable mode** (`-e`), so changes to dependencies take effect immediately after reinstalling.

## For More Information

- **Platform setup guides**: See [docs/platforms/](../../docs/platforms/)
- **Cross-platform patterns**: See [SYSTEM.md](../../SYSTEM.md)
- **Package contents**: See `PACKAGES.md` for curated package list and rationale
