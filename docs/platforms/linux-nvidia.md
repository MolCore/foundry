# Linux + NVIDIA GPU Setup

This guide covers setting up Foundry on Linux servers with NVIDIA GPUs for large-scale compute workloads.

## Use Case

- Large-scale design campaigns (100s-1000s of designs)
- Batch inference jobs
- Training or fine-tuning models
- High-throughput structure prediction

**Not suitable for:** Interactive visualization (use macOS), one-off experiments (use Modal for cost efficiency)

## Prerequisites

- Linux server with NVIDIA GPU(s)
- NVIDIA drivers installed and working
- CUDA toolkit compatible with your drivers (typically CUDA 12.1 or 12.4)
- Python 3.12
- `uv` package manager
- Direct access to database mirrors (recommended)

## Check Your GPU Setup

Before starting, verify your GPU and CUDA setup:

```bash
# Check GPU and driver version
nvidia-smi

# Should show CUDA version (e.g., CUDA Version: 12.9)
# The driver CUDA version is the maximum supported; you can use older CUDA wheels
```

## Installation

### 1. Install System Dependencies

```bash
# Install uv if not already installed
curl -LsSf https://astral.sh/uv/install.sh | sh

# Verify Python 3.12 availability
uv python install 3.12
```

### 2. Create Python Environment

Choose between repo-local env (recommended when developing) or global env:

#### Option A: Repo-Local Environment (Recommended)

```bash
cd /path/to/foundry
uv python install 3.12
uv venv --python 3.12
source .venv/bin/activate
uv pip install -e ".[all,dev]"
```

#### Option B: Global Compute Environment

```bash
uv python install 3.12
uv venv ~/.venvs/molecore_foundry --python 3.12
source ~/.venvs/molecore_foundry/bin/activate
uv pip install -e /path/to/foundry/tools/envs/molecore_foundry
uv pip install -e "/path/to/foundry[all,dev]"
```

### 3. Install CUDA-Enabled PyTorch

**Critical:** The default installation includes CPU-only PyTorch. On GPU servers, upgrade to CUDA-enabled PyTorch.

Choose your CUDA version based on your driver capabilities:

```bash
# For CUDA 12.4 (recommended for most recent drivers)
uv pip install --upgrade torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu124

# OR for CUDA 12.1 (for slightly older drivers)
uv pip install --upgrade torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu121
```

**How to choose:**
- If `nvidia-smi` shows CUDA 12.4+, use `cu124`
- If `nvidia-smi` shows CUDA 12.1-12.3, use `cu121`
- Your driver version shown in `nvidia-smi` is a maximum; you can use any compatible or older CUDA wheel

### 4. Configure Machine-Specific Paths

Create `.envrc.local` for your database paths:

```bash
cd /path/to/foundry
cp .envrc.local.example .envrc.local
```

Edit `.envrc.local` with your Linux server paths:

```bash
# Example: Linux server with direct database access
export CCD_MIRROR_PATH="/runtime/databases/foundry/ccd"
export PDB_MIRROR_PATH="/runtime/databases/foundry/pdb"

# Optional: Custom prompt label
export VIRTUAL_ENV_DISABLE_PROMPT=1
export PS1="(foundry-gpu) ${PS1}"
```

### 5. Enable direnv (Optional but Recommended)

```bash
# Install direnv
curl -sfL https://direnv.net/install.sh | bash

# Add to your shell config (~/.bashrc)
eval "$(direnv hook bash)"

# Allow the repo
cd /path/to/foundry
direnv allow
```

### 6. Download Model Checkpoints

```bash
# Download base models (RFD3, RF3, MPNN)
foundry install base-models

# Or download all available models
foundry install all

# Check what's installed
foundry list-installed
```

## Verification

### Test GPU Access

```bash
python -c "
import torch
print(f'PyTorch: {torch.__version__}')
print(f'CUDA available: {torch.cuda.is_available()}')
print(f'CUDA version: {torch.version.cuda}')
print(f'GPU count: {torch.cuda.device_count()}')
if torch.cuda.is_available():
    print(f'GPU 0: {torch.cuda.get_device_name(0)}')
    print(f'GPU memory: {torch.cuda.get_device_properties(0).total_memory / 1e9:.1f} GB')
"
```

Expected output should show:
```
CUDA available: True
GPU count: 1 (or more)
GPU 0: NVIDIA A100-SXM4-80GB (or your GPU model)
```

### Test Foundry Models

```bash
# Test imports
python -c "
from foundry.models.rfd3 import RFDiffusion3
from foundry.models.rf3 import RosettaFold3
from foundry.models.mpnn import ProteinMPNN
print('✅ All models import successfully')
"

# Test GPU inference (small example)
python -c "
import torch
from foundry.models.rfd3 import RFDiffusion3

device = 'cuda' if torch.cuda.is_available() else 'cpu'
print(f'Using device: {device}')
# Add small inference test here once you have example code
"
```

### Test Database Access

```bash
# Test CCD mirror access
python -c "
import os
print(f'CCD_MIRROR_PATH: {os.getenv(\"CCD_MIRROR_PATH\")}')
print(f'PDB_MIRROR_PATH: {os.getenv(\"PDB_MIRROR_PATH\")}')

from atomworks import Structure
s = Structure.from_pdb('1ubq')
print(f'✅ Loaded structure: {s.id}, {len(s)} atoms')
"
```

## Production Workflows

### Batch Inference

Example: Generate 100 designs with RFD3

```bash
# Run in background with nohup
nohup python scripts/batch_rfd3.py \
    --input target.pdb \
    --num-designs 100 \
    --output-dir results/ \
    --device cuda \
    > rfd3.log 2>&1 &

# Monitor progress
tail -f rfd3.log
```

### Multi-GPU Usage

If you have multiple GPUs, distribute work across them:

```bash
# Use specific GPU
CUDA_VISIBLE_DEVICES=0 python script.py  # Use GPU 0
CUDA_VISIBLE_DEVICES=1 python script.py  # Use GPU 1

# Or parallelize in Python
python scripts/parallel_inference.py --num-gpus 4
```

### Resource Monitoring

Monitor GPU usage during long runs:

```bash
# Real-time GPU monitoring
watch -n 1 nvidia-smi

# Or use more detailed tool
nvtop  # Install: sudo apt install nvtop
```

## Platform-Specific Notes

### No Visualization Tools

This setup intentionally excludes PyMOL and other GUI tools:
- Servers typically don't have display access
- Visualization should be done on your macOS development machine
- For remote visualization, transfer results to macOS or use web-based tools (py3Dmol, NGLview)

### Database Mirrors (Direct Access)

Linux servers typically have direct filesystem access to databases:
```
/runtime/databases/foundry/ccd
/runtime/databases/foundry/pdb
```

This is much faster than network mounts or on-demand fetching.

### Memory Management

For large batch jobs:
```python
# Clear GPU cache between batches
import torch
torch.cuda.empty_cache()

# Monitor memory
torch.cuda.memory_summary()
```

### PyRosetta (Optional)

If you need PyRosetta for specific workflows:

```bash
uv pip install --upgrade pyrosetta-installer
python -c "import pyrosetta_installer; pyrosetta_installer.install_pyrosetta()"
python -c "import pyrosetta; pyrosetta.init('-mute all'); print('✅ PyRosetta OK')"
```

**Note:** This is a large download (~GB) and requires RosettaCommons credentials.

## Troubleshooting

### CUDA Not Available

If `torch.cuda.is_available()` returns `False`:

```bash
# Check if CUDA PyTorch was installed
python -c "import torch; print(torch.version.cuda)"
# Should show "12.4" or "12.1", not None

# If None, reinstall CUDA PyTorch
uv pip install --upgrade torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu124
```

### Out of Memory Errors

```python
# Reduce batch size
batch_size = 1  # Start small

# Use gradient checkpointing (if training)
model.gradient_checkpointing_enable()

# Clear cache regularly
torch.cuda.empty_cache()
```

### Database Access Issues

```bash
# Check if paths exist
ls /runtime/databases/foundry/ccd
ls /runtime/databases/foundry/pdb

# Check environment variables
echo $CCD_MIRROR_PATH
echo $PDB_MIRROR_PATH

# Check permissions
ls -la /runtime/databases/foundry/
```

### Slow Inference

```bash
# Verify GPU is being used
nvidia-smi  # Should show Python process using GPU memory

# Check PyTorch is using GPU
python -c "
import torch
x = torch.randn(1000, 1000).cuda()
y = x @ x  # Matrix multiply on GPU
print('GPU computation working')
"
```

## Performance Optimization

### Mixed Precision Training

```python
from torch.cuda.amp import autocast, GradScaler

scaler = GradScaler()
with autocast():
    # Your training/inference code
    output = model(input)
```

### Optimize Data Loading

```python
from torch.utils.data import DataLoader

loader = DataLoader(
    dataset,
    batch_size=32,
    num_workers=4,  # Parallel data loading
    pin_memory=True,  # Faster CPU->GPU transfer
)
```

## Next Steps

- For interactive development, use your [macOS setup](macos-local.md)
- For serverless production pipelines, see [Modal Cloud](modal-cloud.md)
- Read [SYSTEM.md](../../SYSTEM.md) for cross-platform coordination
- Check `examples/` directory for batch processing scripts
