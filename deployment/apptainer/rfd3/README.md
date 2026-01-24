# RFD3 Apptainer Container for Borg

Minimal Apptainer container for RFDiffusion3 (RFD3) all-atom protein design, optimized for the borg Linux server.

## Overview

This directory contains everything needed to build, validate, and test RFD3 on borg using Apptainer containers.

**Design principles**:
- **Minimal Python environment**: Only essential dependencies (PyTorch + foundry[rfd3])
- **Database bind mounts**: Databases mounted from borg's `/runtime/databases/foundry/` at runtime
- **No root required**: Uses `--fakeroot` flag for building
- **GPU-ready**: CUDA 12.1 support with `--nv` flag

## Files

```
rfd3/
├── Containerfile              # Apptainer definition file
├── build.sh                   # Container build script
├── validate.sh                # Container validation script
├── run_test.sh                # Test execution script (num=2)
├── validate_outputs.sh        # Output validation script
├── test_configs/
│   └── test_num2.json         # Test configuration (2 designs)
├── outputs/                   # Test outputs (created at runtime)
└── README.md                  # This file
```

## Quick Start

### 1. Transfer Files to Borg

From your local machine:

```bash
# SCP the entire rfd3 directory to borg
scp -r /Users/ariel/dev/molCore/workflow/containers/apptainer/rfd3 user@borg:/path/to/destination/

# Or use rsync for better performance
rsync -avz --progress \
    /Users/ariel/dev/molCore/workflow/containers/apptainer/rfd3/ \
    user@borg:/path/to/destination/rfd3/
```

### 2. SSH to Borg and Build Container

```bash
ssh user@borg
cd /path/to/rfd3

# Build container (takes ~15-30 minutes)
./build.sh

# With force rebuild
./build.sh --force
```

**Output**: `/runtime/containers/rfd3.sif` (~2-4 GB)

### 3. Validate Container

```bash
./validate.sh
```

**Tests**:
- ✓ Python 3.10 installed
- ✓ PyTorch + CUDA working
- ✓ RFD3 modules import
- ✓ Checkpoint downloaded
- ✓ Database mount points accessible
- ✓ GPU detected (with `--nv`)

### 4. Run Test Inference (num=2)

```bash
./run_test.sh
```

**What it does**:
- Runs RFD3 with `test_num2.json` config
- Generates 2 de novo monomer designs (80-120 residues)
- Outputs to `./outputs/rfd3_test_TIMESTAMP/`
- Shows GPU usage before/after

**Expected time**: 5-10 minutes for 2 designs on L40S/H200

### 5. Validate Outputs

```bash
# Use the output directory from run_test.sh
./validate_outputs.sh ./outputs/rfd3_test_TIMESTAMP
```

**Checks**:
- ✓ File counts (≥2 CIF files expected)
- ✓ Structure format validity
- ✓ Atom/residue counts
- ✓ JSON metadata parsing
- ✓ File size statistics

## Container Details

### Base Environment
- **Base image**: `nvidia/cuda:12.1.0-devel-ubuntu22.04`
- **Python**: 3.10 via Miniconda
- **CUDA**: 12.1
- **PyTorch**: Latest with CUDA 12.1 support

### Python Packages (Minimal)
- `pytorch` (with CUDA 12.1)
- `rc-foundry[rfd3]` (includes all RFD3 dependencies)
- Dependencies pulled by foundry (minimal)

### Checkpoints
- **RFD3 checkpoint**: Pre-downloaded during build
- **Location**: `/root/.foundry/checkpoints/rfd3_latest.ckpt`
- **Size**: ~500 MB

### Database Requirements

**Must exist on borg host**:
- `/runtime/databases/foundry/pdb/` - PDB mirror
- `/runtime/databases/foundry/ccd/` - CCD chemical components

**Mounted read-only** at runtime with `--bind` flags.

## Usage Examples

### Basic Inference (2 designs)

```bash
./run_test.sh
```

### Custom Configuration

Create your own JSON config in `test_configs/`:

```json
{
    "my_design": {
        "length": "100-150",
        "num_designs": 5
    }
}
```

Then run:

```bash
./run_test.sh my_config
```

### Manual Container Execution

```bash
apptainer exec --nv \
    --bind /runtime/databases/foundry/pdb:/runtime/databases/foundry/pdb:ro \
    --bind /runtime/databases/foundry/ccd:/runtime/databases/foundry/ccd:ro \
    --bind ./test_configs:/workspace/configs:ro \
    --bind ./outputs:/workspace/outputs \
    --env PDB_MIRROR_PATH=/runtime/databases/foundry/pdb \
    --env CCD_MIRROR_PATH=/runtime/databases/foundry/ccd \
    /runtime/containers/rfd3.sif \
    rfd3 design \
        out_dir=/workspace/outputs \
        inputs=/workspace/configs/test_num2.json \
        prevalidate_inputs=True
```

## Troubleshooting

### Container Build Fails

**Error**: "Apptainer build failed"

**Solutions**:
- Check disk space: `df -h /runtime/containers`
- Verify Apptainer version: `apptainer --version` (need ≥1.0.0)
- Try without `--fakeroot`: Build on a system with root access
- Check build logs for specific errors

### CUDA Not Available

**Error**: "CUDA available: False"

**Solutions**:
- Use `--nv` flag: Required for GPU access
- Check NVIDIA drivers: `nvidia-smi`
- Verify CUDA version matches: Container uses CUDA 12.1
- Try different GPU: `CUDA_VISIBLE_DEVICES=1 ./run_test.sh`

### Database Not Found

**Error**: "Database directories not found"

**Solutions**:
- Check paths exist: `ls -ld /runtime/databases/foundry/{pdb,ccd}`
- Verify sync status: Run database sync script
- Check permissions: Must be readable
- Update paths in scripts if databases are elsewhere

### Inference Fails

**Error**: "RFD3 inference failed"

**Solutions**:
- Check GPU memory: RFD3 needs >16GB
- Reduce batch size: Edit config JSON
- Check config validity: `cat test_configs/test_num2.json`
- View RFD3 logs: Check stderr output
- Try simpler design: Use `length: "50-80"` for faster test

### No Output Files Generated

**Error**: "No CIF files found"

**Solutions**:
- Check output directory permissions
- Verify inference completed: Look for "✅ RFD3 complete"
- Check for RFD3 errors: Review command output
- Inspect output directory: `find ./outputs -type f`

## Next Steps

After successful borg validation:

1. ✅ **Borg container works** - All tests passed
2. 📊 **Review outputs** - Check structure quality
3. 🚀 **Proceed to Modal** - Implement Modal version with:
   - Lightweight image (same minimal environment)
   - Databases in persistent Modal volumes
   - Same subprocess-based RFD3 execution

See parent directory plan: `/Users/ariel/.claude/plans/joyful-jingling-garden.md`

## Resources

- **RFD3 Documentation**: Foundry repository `/models/rfd3/docs/`
- **Apptainer Docs**: https://apptainer.org/docs/
- **Workflow Container Patterns**: `../rfdiffusion/Containerfile` (similar setup)
- **Plan File**: `/Users/ariel/.claude/plans/joyful-jingling-garden.md`

## Notes

- Container size: ~2-4 GB (minimal environment + checkpoint)
- Build time: ~15-30 minutes (depending on network for checkpoint download)
- Inference time: ~5-10 minutes for 2 designs on modern GPU
- Database mounts are read-only for safety
- Outputs are written to host filesystem via bind mount
