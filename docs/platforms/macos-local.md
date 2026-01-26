# macOS Local Development Setup

This guide covers setting up Foundry on your MacBook Pro for development, prototyping, and interactive visualization.

## Use Case

- Interactive development with Jupyter notebooks
- Code prototyping and testing
- Structure visualization with PyMOL
- Small-scale inference (CPU-only, suitable for testing)

**Not suitable for:** Large-scale production runs (use Linux GPU or Modal instead)

## Prerequisites

- macOS (tested on Darwin 25.2.0)
- Homebrew (for PyMOL)
- Python 3.12
- `uv` package manager
- Network mount access to databases (optional but recommended)

## Installation

### 1. Install System Dependencies

```bash
# Install uv if not already installed
curl -LsSf https://astral.sh/uv/install.sh | sh

# Install PyMOL for visualization
brew install pymol
```

### 2. Create Python Environment

Choose between repo-local env (recommended when working on Foundry) or global env:

#### Option A: Repo-Local Environment (Recommended)

```bash
cd /Users/ariel/dev/molCore/foundry
uv python install 3.12
uv venv --python 3.12
source .venv/bin/activate
uv pip install -e ".[all,dev]"
```

#### Option B: Global Default Environment

```bash
uv python install 3.12
uv venv ~/.venvs/molecore_foundry --python 3.12
source ~/.venvs/molecore_foundry/bin/activate
uv pip install -e /Users/ariel/dev/molCore/foundry/tools/envs/molecore_foundry
uv pip install -e "/Users/ariel/dev/molCore/foundry[all,dev]"
```

### 3. Configure Machine-Specific Paths

Create `.envrc.local` for your database mirror paths:

```bash
cd /Users/ariel/dev/molCore/foundry
cp .envrc.local.example .envrc.local
```

Edit `.envrc.local` with your macOS-specific paths:

```bash
# Example: Ariel's macOS setup with mounted databases
export CCD_MIRROR_PATH="$HOME/mounts/runtime/databases/foundry/ccd"
export PDB_MIRROR_PATH="$HOME/mounts/runtime/databases/foundry/pdb"

# Optional: Custom prompt label
export VIRTUAL_ENV_DISABLE_PROMPT=1
export PS1="(foundry-mac) ${PS1}"
```

**Note:** Database mirrors are optional. Foundry can fetch structures on-demand, but local mirrors are faster.

### 4. Enable direnv (Optional but Recommended)

If you use direnv for automatic environment activation:

```bash
# Install direnv if needed
brew install direnv

# Add to your shell config (~/.zshrc or ~/.bashrc)
eval "$(direnv hook zsh)"  # or bash

# Allow the repo
cd /Users/ariel/dev/molCore/foundry
direnv allow
```

### 5. Download Model Checkpoints

```bash
# Download base models (RFD3, RF3, MPNN)
foundry install base-models

# Check what's installed
foundry list-installed
```

Checkpoints are stored in `~/.foundry/checkpoints` by default.

## Verification

### Test Basic Installation

```bash
python -c "
import torch
import atomworks
import biotite
import numpy as np
import pandas as pd
from foundry import __version__ as foundry_version

print('✅ Core packages imported successfully')
print(f'PyTorch: {torch.__version__}')
print(f'AtomWorks: {atomworks.__version__}')
print(f'Foundry: {foundry_version}')
print(f'CUDA available: {torch.cuda.is_available()} (Expected: False on macOS)')
"
```

### Test PyMOL Wrapper

```bash
python -c "
import pymolPy3
pm = pymolPy3.pymolPy3()
print('✅ PyMOL wrapper ready')
"
```

### Test Foundry Models

```bash
# Check if checkpoints are accessible
foundry list-installed

# Test RFD3 import (should not error)
python -c "from foundry.models.rfd3 import RFDiffusion3; print('✅ RFD3 imports correctly')"
```

## Development Workflow

### Interactive Notebooks

```bash
# Launch JupyterLab
jupyter lab

# Or Jupyter Notebook
jupyter notebook
```

See `examples/all.ipynb` in the main repo for model usage examples.

### Running Inference

Small-scale CPU inference for testing:

```bash
# Example: Run RFD3 on CPU (slow but works for testing)
python scripts/run_rfd3.py --input target.pdb --num-designs 5
```

**For larger runs:** Use your Linux GPU server or Modal cloud.

### Visualization

PyMOL is available for structure visualization:

```python
import pymolPy3

pm = pymolPy3.pymolPy3()
pm("load structure.pdb")
pm("show cartoon")
pm("color cyan")
```

Or use notebook-friendly alternatives:

```python
import py3Dmol

view = py3Dmol.view(width=400, height=300)
view.addModel(open('structure.pdb', 'r').read(), 'pdb')
view.setStyle({'cartoon': {'color': 'spectrum'}})
view.show()
```

## Platform-Specific Notes

### PyTorch (CPU-only)

macOS uses CPU-only PyTorch by default. This is intentional:
- Sufficient for code development and testing
- GPU-accelerated PyTorch on macOS (MPS backend) has limited compatibility with foundry dependencies
- For production GPU work, use Linux GPU server or Modal

### Database Mirrors (Mounted)

Your setup uses network-mounted database paths:
```
~/mounts/runtime/databases/foundry/ccd
~/mounts/runtime/databases/foundry/pdb
```

If mounts are unavailable, Foundry will fall back to downloading structures from RCSB (slower but functional).

### Memory Considerations

MacBook Pro with limited RAM:
- Reduce batch sizes for inference
- Use smaller design campaigns (5-10 designs instead of 100+)
- Monitor memory with Activity Monitor

## Troubleshooting

### Import Errors

If you see `ModuleNotFoundError`:
```bash
# Ensure you're in the correct environment
which python  # Should show .venv or ~/.venvs path

# Reinstall in editable mode
uv pip install -e ".[all,dev]"
```

### Database Mirror Issues

If AtomWorks can't find structures:
```bash
# Check if mirrors are mounted
ls ~/mounts/runtime/databases/foundry/ccd
ls ~/mounts/runtime/databases/foundry/pdb

# Check environment variables
echo $CCD_MIRROR_PATH
echo $PDB_MIRROR_PATH

# Test without mirrors (on-demand fetching)
unset CCD_MIRROR_PATH PDB_MIRROR_PATH
python -c "from atomworks import Structure; s = Structure.from_pdb('1ubq'); print(s)"
```

### PyMOL Not Found

```bash
# Reinstall PyMOL
brew reinstall pymol

# Test system PyMOL
pymol -c  # Should launch without GUI

# Test wrapper
python -c "import pymolPy3; print('OK')"
```

## Next Steps

- See [examples/all.ipynb](../../examples/all.ipynb) for model usage
- For large-scale runs, set up [Linux GPU](linux-nvidia.md) or [Modal](modal-cloud.md)
- Read [SYSTEM.md](../../SYSTEM.md) for cross-platform coordination patterns
