# Modal Cloud Production Pipeline

This guide covers deploying Foundry on Modal for serverless, scalable production workflows.

## Use Case

- **Production design pipelines**: RFD3 → MPNN → RF3 end-to-end
- **Cost-effective GPU bursts**: Pay per second of GPU usage
- **Parallel execution**: Run 100s of designs simultaneously
- **Reproducible workflows**: Container-based, version-controlled

**Best for:** Production deployments, batch processing, teams needing scalable infrastructure
**Not suitable for:** Interactive development (use macOS), long-running training jobs (use dedicated GPU server)

## Why Modal for Foundry?

Traditional deployment challenges:
- Managing Docker images and registries
- Kubernetes configuration and orchestration
- Provisioning and scaling GPU infrastructure
- Cost of idle GPU servers

Modal solves these by:
- Automatic container building from Python code
- Serverless GPU execution (pay only when running)
- Built-in parallelization primitives
- No infrastructure management

## Prerequisites

- Modal account (sign up at https://modal.com)
- Python 3.12+ locally
- `uv` or `pip` for local development
- Foundry repository cloned locally

## Initial Setup

### 1. Install Modal Locally

```bash
# On your macOS development machine
pip install modal

# Or in your existing foundry environment
uv pip install modal
```

### 2. Authenticate with Modal

```bash
# This opens a browser for authentication
modal setup

# Verify authentication
modal token show
```

### 3. Create Modal Workspace

Set up a workspace for your foundry projects:

```bash
# Create a new workspace (or use existing)
modal workspace create foundry-production

# Set as default
modal workspace use foundry-production
```

## Architecture: Modular Modal Apps

Unlike a monolithic approach (single container with all models), this implementation uses **separate Modal apps** for each foundry model:

```
modal_apps/
├── foundry_rfd3.py              # RFDiffusion3 (A100, ~10GB image)
├── foundry_mpnn.py              # ProteinMPNN (A10G, ~5GB image)
├── foundry_rf3.py               # RosettaFold3 (A100, ~12GB image)
├── pipeline_orchestrator.py     # Coordinates all three
└── README.md                    # Detailed implementation docs
```

### Why Modular?

| Aspect | Monolithic | Modular (Our Approach) |
|--------|------------|------------------------|
| Image size | ~30GB | 5-10GB each |
| Cold start | Slow (pull 30GB) | Fast (pull 5-10GB) |
| GPU optimization | One size fits all | A10G for MPNN, A100 for RFD3/RF3 |
| Update model | Rebuild everything | Rebuild only changed app |
| Parallel scheduling | Limited | Modal can use different GPUs simultaneously |

**Benefits:**
- ✅ Faster cold starts (smaller images)
- ✅ Lower costs (A10G for MPNN is 10x cheaper than A100)
- ✅ Better parallelization across different GPU types
- ✅ Independent model updates

## Pipeline Architecture

```
Target PDB
    ↓
┌───────────────────────────────┐
│  RFD3 (A100)                  │  Generate 100 backbones
│  foundry_rfd3.py              │  30s each × 100 = ~50min
└───────────────────────────────┘
    ↓ (100 backbones)
┌───────────────────────────────┐
│  MPNN (A10G) × 100 parallel   │  Design 10 sequences per backbone
│  foundry_mpnn.py              │  5s each × 1000 = ~83min (parallelized)
└───────────────────────────────┘
    ↓ (1000 sequences)
┌───────────────────────────────┐
│  RF3 (A100) × 1000 parallel   │  Predict structures
│  foundry_rf3.py               │  30s each × 1000 = ~500min (parallelized)
└───────────────────────────────┘
    ↓ (1000 predictions)
Results ranked by pLDDT
```

**Orchestrator** (`pipeline_orchestrator.py`):
- Calls RFD3 → waits for backbones
- Maps MPNN over backbones in parallel
- Maps RF3 over sequences in parallel
- Filters and ranks by confidence metrics

## Quick Start

### Test the Pipeline (Recommended First Step)

```bash
# Test individual models first
cd /path/to/foundry

# Test RFD3 (generates 5 placeholder backbones)
modal run modal_apps/foundry_rfd3.py::test --num-designs 5

# Test MPNN (designs 10 placeholder sequences)
modal run modal_apps/foundry_mpnn.py::test --num-sequences 10

# Test RF3 (predicts 1 placeholder structure)
modal run modal_apps/foundry_rf3.py::test

# Test full pipeline (5 backbones × 2 sequences = 10 designs)
modal run modal_apps/pipeline_orchestrator.py::test
```

**Note:** These use placeholder implementations. You need to add actual foundry inference code (see Implementation Status below).

### Run Production Pipeline

```bash
# Full pipeline: 100 backbones × 10 sequences = 1,000 designs
modal run modal_apps/pipeline_orchestrator.py::run \
    --target-pdb-path target.pdb \
    --num-backbones 100 \
    --sequences-per-backbone 10
```

## Implementation Status

### ✅ Infrastructure Ready

The Modal apps are fully set up with:
- Container image definitions
- GPU configuration (A100 for RFD3/RF3, A10G for MPNN)
- Volume setup for databases and results
- Pipeline orchestration
- CLI entrypoints
- Parallel execution

### ⚠️ TODO: Add Foundry Inference Code

Each app (`foundry_rfd3.py`, `foundry_mpnn.py`, `foundry_rf3.py`) contains placeholder implementations marked with:

```python
# ========================================================================
# TODO: Replace with actual foundry inference code
# ========================================================================
```

**You need to replace these placeholders with actual foundry model calls.**

Expected foundry API structure (adjust based on actual API):

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

See `modal_apps/README.md` for detailed implementation instructions.

## Database Strategy: Modal Volume

For PDB/CCD mirrors, the apps use a Modal Volume with a curated subset of essential structures.

### Setup Database Volume (One-Time)

```python
# Create the volume
from modal import Volume
volume = Volume.from_name("foundry-databases", create_if_missing=True)

# Option 1: Populate via Modal function
@app.function(volumes={"/databases": volume}, timeout=3600)
def setup_databases():
    from pathlib import Path

    # Download essential structures
    ccd_path = Path("/databases/ccd")
    pdb_path = Path("/databases/pdb")
    ccd_path.mkdir(parents=True, exist_ok=True)
    pdb_path.mkdir(parents=True, exist_ok=True)

    # TODO: Download CCD dictionary
    # TODO: Download essential PDB structures (curate list)

    volume.commit()
    print("✅ Databases populated")

# Option 2: Mount volume locally and copy files
# modal volume put foundry-databases local_ccd_dir /ccd
# modal volume put foundry-databases local_pdb_dir /pdb
```

### Alternative: On-Demand Fetching

If you don't need many structures, skip the volume and fetch on-demand:

```python
# AtomWorks can download structures automatically
from atomworks import Structure
structure = Structure.from_pdb("1ubq")  # Downloads from RCSB
```

This is simpler but slower for large-scale pipelines.

## GPU Configuration & Costs

| Model | GPU | Memory | Cost/hr* | Stage Cost (1000 designs) |
|-------|-----|--------|----------|---------------------------|
| RFD3 | A100 | 40GB | ~$2.50 | ~$2.50 (50 min) |
| MPNN | A10G | 24GB | ~$0.30 | ~$0.42 (83 min) |
| RF3 | A100 | 40GB | ~$2.50 | ~$21 (500 min) |

*Approximate Modal pricing (check current rates)

**Total cost for 1,000 designs: ~$24**

**Cost optimization tips:**
- Use A10G for MPNN (10x cheaper than A100)
- Parallelize MPNN and RF3 stages to reduce wall time
- Batch multiple sequences per GPU call
- Keep container images small for fast cold starts

## Monitoring & Debugging

### View Logs

```bash
# Real-time logs for orchestrator
modal logs foundry-pipeline

# Logs for individual apps
modal logs foundry-rfd3
modal logs foundry-mpnn
modal logs foundry-rf3
```

### Check Containers

```bash
# List running containers
modal container list

# Stop a container
modal container stop <container-id>
```

### Volume Management

```bash
# List volume contents
modal volume ls foundry-databases
modal volume ls foundry-results

# Download results locally
modal volume get foundry-results /results/pipeline ./local_results

# Upload files to volume
modal volume put foundry-databases ./local_file.pdb /databases/pdb/
```

## Deployment Options

### Interactive (Recommended for Development)

Run functions on-demand without persistent deployment:

```bash
modal run modal_apps/pipeline_orchestrator.py::run \
    --target-pdb-path target.pdb
```

Modal automatically:
1. Builds images (first time only, then cached)
2. Spins up GPUs on-demand
3. Runs your pipeline
4. Shuts down GPUs when done

### Persistent Deployment (For Production API)

Deploy apps to make them callable via Modal API:

```bash
# Deploy all apps
modal deploy modal_apps/foundry_rfd3.py
modal deploy modal_apps/foundry_mpnn.py
modal deploy modal_apps/foundry_rf3.py
modal deploy modal_apps/pipeline_orchestrator.py

# Now callable via Modal web dashboard or API
```

## Troubleshooting

### Image Build Failures

```bash
# Test image build
modal app build modal_apps/foundry_rfd3.py

# View build logs
modal app logs foundry-rfd3
```

### GPU Out of Memory

Upgrade to A100-80GB or reduce batch size:

```python
@app.function(gpu="A100-80GB")  # Double memory
```

### Slow Cold Starts

- Keep images small (separate apps helps)
- Bake checkpoints into images
- Use persistent deployment for frequently-used functions

### Placeholder Warnings

If you see:
```
⚠️  WARNING: Using placeholder RFD3 implementation
```

You need to replace placeholder code with actual foundry inference. See `modal_apps/README.md` for details.

## Next Steps

1. **Implement model inference**: Replace placeholders in each app
   - `modal_apps/foundry_rfd3.py` (~line 80)
   - `modal_apps/foundry_mpnn.py` (~line 80)
   - `modal_apps/foundry_rf3.py` (~line 80)

2. **Test individual models**: Verify each model works independently
   ```bash
   modal run modal_apps/foundry_rfd3.py::test
   modal run modal_apps/foundry_mpnn.py::test
   modal run modal_apps/foundry_rf3.py::test
   ```

3. **Test pipeline**: Run small-scale test
   ```bash
   modal run modal_apps/pipeline_orchestrator.py::test
   ```

4. **Scale up**: Run production pipeline (100+ backbones)
   ```bash
   modal run modal_apps/pipeline_orchestrator.py::run \
       --target-pdb-path target.pdb \
       --num-backbones 100
   ```

5. **Optimize**: Tune batch sizes, GPU selection, and parallel execution

## Example Workflow

```bash
# 1. Authenticate with Modal (one-time)
modal setup

# 2. Test individual components with placeholders
modal run modal_apps/foundry_rfd3.py::test
modal run modal_apps/foundry_mpnn.py::test
modal run modal_apps/foundry_rf3.py::test

# 3. Implement actual foundry inference code
# (Edit modal_apps/foundry_*.py files)

# 4. Test with real foundry models
modal run modal_apps/pipeline_orchestrator.py::test

# 5. Run production pipeline
modal run modal_apps/pipeline_orchestrator.py::run \
    --target-pdb-path my_target.pdb \
    --num-backbones 100 \
    --sequences-per-backbone 10

# 6. Download results
modal volume get foundry-results /results/pipeline ./results

# 7. Analyze top designs
cat results/pipeline_summary.json
cat results/top_10_designs.json
```

## Resources

- **Implementation details**: See `modal_apps/README.md`
- **Modal docs**: https://modal.com/docs
- **Modal examples**: https://github.com/modal-labs/modal-examples
- **Modal pricing**: https://modal.com/pricing
- **Platform comparison**: See [docs/platforms/README.md](README.md)

## Comparison with Other Platforms

| Feature | Modal Cloud | Linux GPU Server | macOS Local |
|---------|-------------|------------------|-------------|
| Setup time | Minutes | Hours | Minutes |
| GPU access | On-demand (any GPU) | Fixed hardware | None (CPU only) |
| Scaling | Automatic (100s of parallel) | Manual | N/A |
| Cost | Pay-per-second (~$24/1000 designs) | Fixed (24/7) | Free (local) |
| Parallelization | Native (Modal .map()) | Manual (multiprocessing) | N/A |
| Cold start | Fast (5-10GB images) | N/A (always on) | N/A |
| Best for | Production pipelines, bursts | Long training, batch jobs | Development, testing |

Modal is ideal for production pipelines where you need:
- Scalability without infrastructure management
- Cost efficiency (pay only when running)
- Parallel execution across heterogeneous GPUs
- Reproducible, version-controlled workflows
