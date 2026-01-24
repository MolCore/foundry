# Foundry Deployment

Multi-platform deployment configurations for foundry models (RFD3, MPNN, RF3).

## Architecture

Each model has **two deployment methods**:
1. **Apptainer** - HPC/SLURM deployment (borg, clusters)
2. **Modal** - Cloud serverless deployment (Modal.com)

Both use the **same databases and checkpoints** but different container technologies.

## Directory Structure

```
deployment/
├── apptainer/           # HPC containers (Singularity/Apptainer)
│   ├── rfd3/           # RFD3 container + scripts
│   ├── mpnn/           # MPNN container (future)
│   └── rf3/            # RF3 container (future)
├── modal/              # Cloud deployment (Modal)
│   ├── rfd3/           # RFD3 Modal app
│   ├── mpnn/           # MPNN Modal app (future)
│   └── rf3/            # RF3 Modal app (future)
└── README.md           # This file
```

## Shared Resources

### On Borg (/runtime/)
```
/runtime/
├── containers/         # Built .sif files (auto-updated via CI/CD)
│   ├── rfd3.sif
│   ├── mpnn.sif
│   └── rf3.sif
├── databases/foundry/  # Shared databases
│   ├── pdb/
│   └── ccd/
└── checkpoints/        # Model checkpoints
```

### On Modal (volumes)
```
Modal volumes:
├── /databases          # Same databases uploaded from borg
└── /checkpoints        # Same checkpoints
```

## Deployment Workflows

### Apptainer (HPC)
1. Build container: `cd apptainer/rfd3 && ./build.sh`
2. Validate: `./validate.sh`
3. Test: `./run_test.sh`
4. Deploy to borg: Container built at `/runtime/containers/rfd3.sif`

### Modal (Cloud)
1. Update Modal app: `cd modal/rfd3`
2. Deploy: `modal deploy rfd3_app.py`
3. Test: `modal run rfd3_app.py::test`

## CI/CD (Future)

Automated deployment on model updates:
```yaml
# .github/workflows/deploy-rfd3.yml
on:
  push:
    paths: ['models/rfd3/**']
jobs:
  - Build Apptainer container
  - Push to borg:/runtime/containers/
  - Deploy Modal app
  - Update workflow repo registry
```

## Current Status

- ✅ **RFD3 Apptainer**: Ready for borg testing
- ⏳ **RFD3 Modal**: After borg validation
- ⏳ **MPNN**: Not started
- ⏳ **RF3**: Not started

## See Also

- **Apptainer deployment**: `apptainer/rfd3/README.md`
- **Modal deployment**: `modal/rfd3/README.md` (future)
- **Plan file**: `/Users/ariel/.claude/plans/joyful-jingling-garden.md`
