#!/bin/bash
#
# Validate RFD3 Apptainer container on borg
# Tests: Python, CUDA, PyTorch, RFD3 imports, checkpoint, databases
#

set -e

CONTAINER_SIF="/runtime/containers/rfd3.sif"

echo "========================================="
echo "RFD3 Container Validation"
echo "========================================="
echo "Container: $CONTAINER_SIF"
echo ""

# Test 1: Container exists
echo "[1/7] Checking container file..."
if [[ ! -f "$CONTAINER_SIF" ]]; then
    echo "❌ ERROR: Container not found: $CONTAINER_SIF"
    echo ""
    echo "Build the container first:"
    echo "  ./build.sh"
    exit 1
fi
echo "✓ Container file exists ($(du -h "$CONTAINER_SIF" | cut -f1))"
echo ""

# Test 2: Python version
echo "[2/7] Checking Python version..."
PYTHON_VERSION=$(apptainer exec "$CONTAINER_SIF" python --version 2>&1)
echo "✓ $PYTHON_VERSION"
echo ""

# Test 3: CUDA availability
echo "[3/7] Testing CUDA and PyTorch..."
apptainer exec --nv "$CONTAINER_SIF" python -c "
import sys
import torch

print('PyTorch version:', torch.__version__)
print('CUDA available:', torch.cuda.is_available())

if not torch.cuda.is_available():
    print('⚠️  WARNING: CUDA not available!')
    print('   Make sure to use --nv flag and have NVIDIA drivers installed')
    sys.exit(0)  # Don't fail, just warn

print('CUDA version:', torch.version.cuda)
print('Number of GPUs:', torch.cuda.device_count())

if torch.cuda.device_count() > 0:
    print('GPU 0:', torch.cuda.get_device_name(0))
    props = torch.cuda.get_device_properties(0)
    print('GPU memory:', f'{props.total_memory / 1e9:.1f} GB')
    print('Compute capability:', f'{props.major}.{props.minor}')

print('✓ CUDA test passed')
"
echo ""

# Test 4: Foundry and RFD3 imports
echo "[4/7] Testing foundry and RFD3 imports..."
apptainer exec "$CONTAINER_SIF" python -c "
from rfd3.engine import RFD3InferenceEngine, RFD3InferenceConfig
from rfd3.trainer.rfd3 import AADesignTrainer
print('✓ RFD3 imports successful')
"
echo ""

# Test 5: RFD3 checkpoint
echo "[5/7] Testing RFD3 checkpoint..."
apptainer exec "$CONTAINER_SIF" python -c "
import os
from pathlib import Path

ckpt_dir = Path.home() / '.foundry' / 'checkpoints'
if not ckpt_dir.exists():
    print(f'❌ ERROR: Checkpoint directory not found: {ckpt_dir}')
    exit(1)

ckpt_files = list(ckpt_dir.glob('rfd3*.ckpt'))
if not ckpt_files:
    print(f'❌ ERROR: No RFD3 checkpoint found in {ckpt_dir}')
    print('Expected file matching: rfd3*.ckpt')
    exit(1)

ckpt_file = ckpt_files[0]
file_size_mb = ckpt_file.stat().st_size / (1024 * 1024)
print(f'✓ Found checkpoint: {ckpt_file.name}')
print(f'  Size: {file_size_mb:.1f} MB')
print(f'  Path: {ckpt_file}')
"
echo ""

# Test 6: Database mount points (with bind mounts)
echo "[6/7] Testing database mount points..."
if [[ -d "/runtime/databases/foundry/pdb" ]] && [[ -d "/runtime/databases/foundry/ccd" ]]; then
    apptainer exec \
        --bind /runtime/databases/foundry:/runtime/databases/foundry:ro \
        "$CONTAINER_SIF" \
        bash -c '
        echo "✓ Database directories mounted successfully:"
        ls -ld /runtime/databases/foundry/pdb/ /runtime/databases/foundry/ccd/

        # Check if databases have content
        PDB_COUNT=$(find /runtime/databases/foundry/pdb/ -name "*.cif*" 2>/dev/null | head -5 | wc -l)
        CCD_COUNT=$(find /runtime/databases/foundry/ccd/ -name "*.cif" 2>/dev/null | head -5 | wc -l)

        if [[ $PDB_COUNT -gt 0 ]]; then
            echo "✓ PDB database has content (found $PDB_COUNT sample files)"
        else
            echo "⚠️  WARNING: PDB database appears empty"
        fi

        if [[ $CCD_COUNT -gt 0 ]]; then
            echo "✓ CCD database has content (found $CCD_COUNT sample files)"
        else
            echo "⚠️  WARNING: CCD database appears empty"
        fi
        '
else
    echo "⚠️  WARNING: Database directories not found on host:"
    echo "   Expected: /runtime/databases/foundry/pdb"
    echo "   Expected: /runtime/databases/foundry/ccd"
    echo "   Skipping database mount test"
fi
echo ""

# Test 7: RFD3 command availability
echo "[7/7] Testing rfd3 command..."
apptainer exec "$CONTAINER_SIF" bash -c '
if command -v rfd3 &> /dev/null; then
    echo "✓ rfd3 command found"
    rfd3 --help > /dev/null 2>&1 || true
else
    echo "❌ ERROR: rfd3 command not found in PATH"
    exit 1
fi
'
echo ""

# Summary
echo "========================================="
echo "✅ Validation Complete!"
echo "========================================="
echo ""
echo "All checks passed. Container is ready for testing."
echo ""
echo "Next steps:"
echo "  1. Run inference test: ./run_test.sh"
echo "  2. Validate outputs: ./validate_outputs.sh <output_dir>"
echo ""
