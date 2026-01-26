# Foundry Modal Apps

Modular Modal applications for running foundry models on serverless GPU infrastructure.

## Architecture

Each foundry model runs in a **separate Modal app** with its own optimized container:

```
modal_apps/
├── foundry_rfd3.py              # RFDiffusion3 (A100)
├── foundry_mpnn.py              # ProteinMPNN (A10G)
├── foundry_rf3.py               # RosettaFold3 (A100)
├── pipeline_orchestrator.py     # Coordinates all three
└── README.md                    # This file
```

### Why Separate Apps?

| Approach | Image Size | Cold Start | Flexibility | Cost |
|----------|-----------|------------|-------------|------|
| **Monolithic** (all models in one image) | ~30GB | Slow | Low | Higher |
| **Modular** (separate apps) | ~5-10GB each | Fast | High | Lower |

**Benefits of modular architecture:**
- ✅ Smaller container images (faster cold starts)
- ✅ Independent updates (don't rebuild everything when one model changes)
- ✅ Optimized GPU selection per model (A10G for MPNN, A100 for RFD3/RF3)
- ✅ Better parallelization (Modal can schedule across different GPUs simultaneously)
- ✅ Easier testing (test each model independently)

## Quick Start

### 1. Install Modal Locally

```bash
# On your development machine (macOS)
pip install modal

# Authenticate
modal setup
```

### 2. Test Individual Models

Test each model separately before running the full pipeline:

```bash
# Test RFD3 backbone generation (placeholder)
modal run modal_apps/foundry_rfd3.py::test --num-designs 5

# Test MPNN sequence design (placeholder)
modal run modal_apps/foundry_mpnn.py::test --num-sequences 10

# Test RF3 structure prediction (placeholder)
modal run modal_apps/foundry_rf3.py::test
```

**Note:** These currently use placeholder implementations. You need to add actual foundry inference code (see Implementation section below).

### 3. Test the Full Pipeline

```bash
# Quick test (5 backbones × 2 sequences = 10 designs)
modal run modal_apps/pipeline_orchestrator.py::test

# Production run (100 backbones × 10 sequences = 1,000 designs)
modal run modal_apps/pipeline_orchestrator.py::run \\
    --target-pdb-path path/to/target.pdb \\
    --num-backbones 100 \\
    --sequences-per-backbone 10
```

## Implementation Status

### ✅ Infrastructure Ready
- Modal app structure
- Container image definitions
- GPU configuration (A100 for RFD3/RF3, A10G for MPNN)
- Volume setup for databases and results
- Pipeline orchestration
- CLI entrypoints

### ⚠️ TODO: Add Foundry Inference Code

Each app has placeholder implementations marked with:
```python
# ========================================================================
# TODO: Replace with actual foundry inference code
# ========================================================================
```

You need to replace these with actual foundry model calls. See the comments in each file for the expected structure.

**Files to update:**
1. `foundry_rfd3.py` - Lines ~80-120: Add RFD3 generation code
2. `foundry_mpnn.py` - Lines ~80-120: Add MPNN sequence design code
3. `foundry_rf3.py` - Lines ~80-120: Add RF3 structure prediction code

**Expected foundry API** (adjust based on actual API):
```python
# RFD3
from foundry.models.rfd3 import RFDiffusion3
model = RFDiffusion3.from_pretrained("rfd3-base")
backbone = model.generate(target=structure, num_steps=50, ...)

# MPNN
from foundry.models.mpnn import ProteinMPNN
model = ProteinMPNN.from_pretrained("mpnn-base")
sequences = model.design(backbone=structure, temperature=0.1, ...)

# RF3
from foundry.models.rf3 import RosettaFold3
model = RosettaFold3.from_pretrained("rf3-base")
prediction = model.predict(sequence=seq, num_recycles=3, ...)
```

## Container Images

Each app builds a specialized container image:

### RFD3 Image (~10GB)
- Python 3.12
- PyTorch with CUDA
- Foundry RFD3 dependencies
- RFD3 checkpoint (baked in)

### MPNN Image (~5GB)
- Python 3.12
- PyTorch with CUDA
- Foundry MPNN dependencies
- MPNN checkpoint (baked in)

### RF3 Image (~12GB)
- Python 3.12
- PyTorch with CUDA
- Foundry RF3 dependencies
- RF3 checkpoint (baked in)

Images are built automatically when you first run a Modal app. After the initial build, they're cached for fast cold starts.

## GPU Configuration

| Model | GPU Type | Memory | Cost/hr (approx) | Use Case |
|-------|----------|--------|------------------|----------|
| RFD3 | A100 (40GB) | 40GB | ~$2-3 | Diffusion (memory-intensive) |
| MPNN | A10G (24GB) | 24GB | ~$0.30 | Inverse folding (lightweight) |
| RF3 | A100 (40GB) | 40GB | ~$2-3 | Structure prediction |

**Cost optimization:**
- MPNN uses A10G (10x cheaper than A100)
- Only pay for GPU time when actually running
- Parallel execution minimizes total wall time

**Example cost for 1,000 designs:**
- RFD3: 100 backbones × 30s = 50min on A100 ≈ $2.50
- MPNN: 1000 sequences × 5s = 83min on A10G ≈ $0.42
- RF3: 1000 predictions × 30s = 500min on A100 ≈ $25
- **Total: ~$28 for 1,000 designs**

## Database Strategy

The pipeline uses a Modal Volume for PDB/CCD database mirrors:

### Setup Database Volume (One-time)

```python
# Create and populate the volume
# (You need to implement this based on your requirements)

from modal import Volume
volume = Volume.from_name("foundry-databases", create_if_missing=True)

# Mount locally and copy databases
# OR write a Modal function to download essential structures
```

### Alternative: On-Demand Fetching

If you don't want to maintain a database volume, foundry can fetch structures on-demand from RCSB:

```python
# In your foundry code
from atomworks import Structure
structure = Structure.from_pdb("1ubq")  # Downloads automatically
```

This is simpler but slower for large-scale pipelines.

## Deployment

### Interactive Deployment (Recommended for Development)

Run functions directly without deployment:

```bash
modal run modal_apps/pipeline_orchestrator.py::run \\
    --target-pdb-path target.pdb
```

Modal will:
1. Build images (first time only)
2. Spin up GPUs on-demand
3. Run your pipeline
4. Shut down GPUs when done

### Persistent Deployment (For Production)

Deploy apps to make them callable via API:

```bash
# Deploy individual apps
modal deploy modal_apps/foundry_rfd3.py
modal deploy modal_apps/foundry_mpnn.py
modal deploy modal_apps/foundry_rf3.py
modal deploy modal_apps/pipeline_orchestrator.py

# Now you can call via Modal API or web dashboard
```

## Monitoring

```bash
# View real-time logs
modal logs foundry-pipeline

# Check running containers
modal container list

# View volume contents
modal volume ls foundry-databases
modal volume ls foundry-results

# Download results locally
modal volume get foundry-results /results/pipeline ./local_results
```

## Troubleshooting

### Image Build Failures

```bash
# Test image build without running
modal app build modal_apps/foundry_rfd3.py

# View build logs
modal app logs foundry_rfd3
```

### Import Errors

Make sure foundry is installed in the container image:

```python
# In foundry_*.py
image = modal.Image.debian_slim(python_version="3.12").pip_install(
    "rc-foundry[all]",  # Or your local editable install path
)
```

### GPU Out of Memory

Reduce batch sizes or upgrade to A100-80GB:

```python
@app.function(gpu="A100-80GB")  # Double memory
```

### Placeholder Warnings

If you see:
```
⚠️  WARNING: Using placeholder RFD3 implementation
```

This means you need to replace the placeholder code with actual foundry inference (see Implementation Status above).

## Next Steps

1. **Implement model inference**: Replace placeholders with actual foundry code
2. **Test individual models**: Run each app separately to verify
3. **Test pipeline**: Run small-scale test (5 backbones)
4. **Scale up**: Run production pipeline (100+ backbones)
5. **Optimize**: Tune batch sizes, GPU types, and parallel execution

## Resources

- [Modal Documentation](https://modal.com/docs)
- [Foundry Setup Guide](../docs/platforms/modal-cloud.md)
- [Modal Examples](https://github.com/modal-labs/modal-examples)
- [GPU Pricing](https://modal.com/pricing)
