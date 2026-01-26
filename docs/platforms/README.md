# Platform-Specific Setup

This fork of Foundry supports multiple platforms for different use cases. Choose your platform based on where you'll be working:

## Quick Decision Guide

| Platform | Use Case | GPU | Setup Complexity |
|----------|----------|-----|------------------|
| **[macOS Local](macos-local.md)** | Development, prototyping, visualization | CPU only | Low |
| **[Linux + NVIDIA](linux-nvidia.md)** | Large-scale compute, batch jobs | CUDA GPUs | Medium |
| **[Modal Cloud](modal-cloud.md)** | Production pipelines, serverless GPU | On-demand (A10G/A100) | Medium |

## Platform Details

### macOS Local
**Best for:** Daily development, interactive notebooks, structure visualization

- CPU-only PyTorch (sufficient for prototyping)
- PyMOL installed via Homebrew for visualization
- Database mirrors accessed via mounted network paths
- Fast iteration on code changes

→ **[macOS Setup Guide](macos-local.md)**

### Linux + NVIDIA GPUs
**Best for:** Large-scale design campaigns, training, batch inference

- CUDA-enabled PyTorch for GPU acceleration
- Direct access to database mirrors on server filesystem
- Designed for compute-focused workflows (no visualization tools)
- Can run 100s of designs in parallel

→ **[Linux + NVIDIA Setup Guide](linux-nvidia.md)**

### Modal Cloud
**Best for:** Production pipelines, cost-effective GPU bursts, reproducible workflows

- Serverless GPU execution (pay per second)
- Pre-built container images with model checkpoints
- Parallel execution across multiple GPUs
- Example: RFD3 → MPNN → RF3 design pipeline

→ **[Modal Cloud Setup Guide](modal-cloud.md)**

## Cross-Platform Coordination

All platforms share the same git repository. Machine-specific paths and configurations are managed via:

- **`.envrc.local`** (gitignored) - Your machine-specific environment variables
- **`SYSTEM.md`** - Cross-platform collaboration patterns using direnv

See **[SYSTEM.md](../../SYSTEM.md)** for details on keeping your setup portable across machines.

## Prerequisites (All Platforms)

- Python 3.12
- `uv` package manager
- Access to model checkpoints (see main README.md)

## Getting Started

1. Choose your platform from the table above
2. Follow the platform-specific setup guide
3. Set up `.envrc.local` for machine-specific paths (see [SYSTEM.md](../../SYSTEM.md))
4. Verify installation with the test commands in your platform guide
