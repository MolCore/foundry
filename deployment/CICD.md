# CI/CD Pipeline for Foundry Deployment

## Overview

This document describes the automated Continuous Integration and Continuous Deployment (CI/CD) pipeline for scaling Foundry model deployments across HPC (Apptainer) and Cloud (Modal) platforms.

**Key Principle**: Each model repository (foundry, omegafold, esm, etc.) owns both its Apptainer container definition AND Modal image definition. CI/CD automatically builds, tests, and deploys to both platforms when models are updated.

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                     Model Repository                         │
│                   (e.g., foundry/rfd3)                       │
│                                                              │
│  ├── deployment/apptainer/rfd3/Containerfile                │
│  └── deployment/modal/rfd3/app.py                           │
└───────────────┬─────────────────────────────────────────────┘
                │
                │ git push (trigger)
                ▼
┌─────────────────────────────────────────────────────────────┐
│              GitHub Actions CI/CD Workflow                   │
│                                                              │
│  1. Detect changes to model code                            │
│  2. Build Apptainer container (.sif)                         │
│  3. Run validation tests                                     │
│  4. Deploy to borg (/runtime/containers/)                    │
│  5. Deploy Modal image (modal deploy)                        │
│  6. Update workflow repo registry                            │
└───────────────┬─────────────────────────────────────────────┘
                │
                ├─────────────────┬─────────────────┐
                ▼                 ▼                 ▼
        ┌──────────────┐  ┌──────────────┐  ┌──────────────┐
        │  Borg (HPC)  │  │    Modal     │  │   Workflow   │
        │              │  │   (Cloud)    │  │     Repo     │
        │ /runtime/    │  │              │  │              │
        │ containers/  │  │ Modal.com    │  │  Registry    │
        │ rfd3.sif     │  │ deployment   │  │  Update      │
        └──────────────┘  └──────────────┘  └──────────────┘
```

## Deployment Targets

### 1. HPC Deployment (Borg)
- **Container format**: Apptainer `.sif` files
- **Location**: `/runtime/containers/rfd3.sif`
- **Databases**: `/runtime/databases/foundry/` (shared across all models)
- **Checkpoints**: Embedded in container at `/root/.foundry/checkpoints/`
- **Access**: SSH-based deployment via GitHub Actions self-hosted runner

### 2. Cloud Deployment (Modal)
- **Container format**: Docker-based Modal images
- **Databases**: Modal volumes (`/databases/pdb`, `/databases/ccd`)
- **Checkpoints**: Embedded in image for fast cold starts
- **Deployment**: `modal deploy` command from CI/CD workflow

### 3. Workflow Registry
- **Repository**: `MolCore/workflow`
- **Purpose**: Central registry of available containers and their versions
- **Update**: Automatic PR to workflow repo with new container metadata

## Trigger Conditions

CI/CD pipeline triggers on:

1. **Model code changes**: Any changes to `models/rfd3/`, `models/mpnn/`, etc.
2. **Deployment config changes**: Changes to `deployment/apptainer/` or `deployment/modal/`
3. **Manual trigger**: Workflow dispatch for rebuilds and optional cleanup

## GitHub Actions Workflows

### Workflow 1: Build and Deploy RFD3

**File**: `.github/workflows/deploy-rfd3.yml`

```yaml
name: Deploy RFD3 Container

on:
  push:
    branches:
      - production
    paths:
      - 'models/rfd3/**'
      - 'deployment/apptainer/rfd3/**'
      - 'deployment/modal/rfd3/**'
      - '.github/workflows/deploy-rfd3.yml'
  workflow_dispatch:
    inputs:
      force_rebuild:
        description: 'Force rebuild even if container exists'
        required: false
        type: boolean
        default: false

env:
  MODEL_NAME: rfd3
  CONTAINER_PATH: /runtime/containers/rfd3.sif
  BORG_HOST: borg
  BORG_USER: arielbs10

jobs:
  #############################################################################
  # JOB 1: Build Apptainer Container
  #############################################################################
  build-apptainer:
    name: Build Apptainer Container
    runs-on: self-hosted  # GitHub runner on borg server
    timeout-minutes: 60

    steps:
      - name: Checkout repository
        uses: actions/checkout@v4

      - name: Setup Apptainer
        run: |
          # Verify apptainer is available
          apptainer --version

      - name: Build container
        working-directory: deployment/apptainer/${{ env.MODEL_NAME }}
        run: |
          echo "Building ${{ env.MODEL_NAME }} container..."
          ./build.sh

      - name: Validate container
        working-directory: deployment/apptainer/${{ env.MODEL_NAME }}
        run: |
          echo "Validating container infrastructure..."
          ./validate.sh

      - name: Run test inference
        working-directory: deployment/apptainer/${{ env.MODEL_NAME }}
        run: |
          echo "Running test inference (num=2)..."
          ./run_test.sh

      - name: Validate outputs
        working-directory: deployment/apptainer/${{ env.MODEL_NAME }}
        run: |
          echo "Validating test outputs..."
          LATEST_OUTPUT=$(ls -td outputs/rfd3_test_* | head -1)
          ./validate_outputs.sh "$LATEST_OUTPUT"

      - name: Deploy to borg
        run: |
          echo "Container already built at ${{ env.CONTAINER_PATH }}"
          ls -lh ${{ env.CONTAINER_PATH }}

      - name: Generate container metadata
        id: metadata
        run: |
          # Extract metadata for workflow registry
          CONTAINER_SIZE=$(stat -c%s "${{ env.CONTAINER_PATH }}" 2>/dev/null || stat -f%z "${{ env.CONTAINER_PATH }}")
          CONTAINER_HASH=$(sha256sum "${{ env.CONTAINER_PATH }}" | cut -d' ' -f1)
          BUILD_DATE=$(date -u +"%Y-%m-%dT%H:%M:%SZ")

          echo "size=$CONTAINER_SIZE" >> $GITHUB_OUTPUT
          echo "hash=$CONTAINER_HASH" >> $GITHUB_OUTPUT
          echo "build_date=$BUILD_DATE" >> $GITHUB_OUTPUT

      - name: Upload build artifacts
        uses: actions/upload-artifact@v4
        with:
          name: container-metadata
          path: |
            deployment/apptainer/${{ env.MODEL_NAME }}/outputs/

    outputs:
      container_size: ${{ steps.metadata.outputs.size }}
      container_hash: ${{ steps.metadata.outputs.hash }}
      build_date: ${{ steps.metadata.outputs.build_date }}

  #############################################################################
  # JOB 2: Deploy Modal App
  #############################################################################
  deploy-modal:
    name: Deploy Modal App
    runs-on: ubuntu-latest
    needs: build-apptainer  # Only deploy to Modal after Apptainer validation
    timeout-minutes: 30

    steps:
      - name: Checkout repository
        uses: actions/checkout@v4

      - name: Setup Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.12'

      - name: Install Modal
        run: |
          pip install modal

      - name: Configure Modal credentials
        run: |
          # Modal token from GitHub secrets
          modal token set --token-id ${{ secrets.MODAL_TOKEN_ID }} \
                          --token-secret ${{ secrets.MODAL_TOKEN_SECRET }}

      - name: Deploy Modal app
        working-directory: deployment/modal/${{ env.MODEL_NAME }}
        run: |
          echo "Deploying ${{ env.MODEL_NAME }} to Modal..."
          modal deploy app.py

      - name: Test Modal deployment
        working-directory: deployment/modal/${{ env.MODEL_NAME }}
        run: |
          echo "Running Modal test inference..."
          modal run app.py::test_inference

  #############################################################################
  # JOB 3: Update Workflow Registry
  #############################################################################
  update-workflow-registry:
    name: Update Workflow Registry
    runs-on: ubuntu-latest
    needs: [build-apptainer, deploy-modal]
    timeout-minutes: 10

    steps:
      - name: Checkout workflow repository
        uses: actions/checkout@v4
        with:
          repository: MolCore/workflow
          token: ${{ secrets.WORKFLOW_REPO_TOKEN }}
          path: workflow

      - name: Update container registry
        working-directory: workflow
        run: |
          # Create/update registry entry
          cat > containers/registry/${{ env.MODEL_NAME }}.json <<EOF
          {
            "model": "${{ env.MODEL_NAME }}",
            "version": "${{ github.sha }}",
            "build_date": "${{ needs.build-apptainer.outputs.build_date }}",
            "container": {
              "path": "${{ env.CONTAINER_PATH }}",
              "size": ${{ needs.build-apptainer.outputs.container_size }},
              "hash": "${{ needs.build-apptainer.outputs.container_hash }}"
            },
            "platforms": {
              "apptainer": {
                "available": true,
                "location": "borg:/runtime/containers/rfd3.sif"
              },
              "modal": {
                "available": true,
                "deployment": "foundry-rfd3"
              }
            }
          }
          EOF

      - name: Create Pull Request
        uses: peter-evans/create-pull-request@v6
        with:
          token: ${{ secrets.WORKFLOW_REPO_TOKEN }}
          path: workflow
          commit-message: "Update ${{ env.MODEL_NAME }} container registry"
          branch: update-${{ env.MODEL_NAME }}-${{ github.sha }}
          title: "Update ${{ env.MODEL_NAME }} container to ${{ github.sha }}"
          body: |
            Automated update from foundry repository.

            **Container**: `${{ env.MODEL_NAME }}`
            **Version**: `${{ github.sha }}`
            **Build date**: ${{ needs.build-apptainer.outputs.build_date }}
            **Size**: ${{ needs.build-apptainer.outputs.container_size }} bytes
            **Hash**: `${{ needs.build-apptainer.outputs.container_hash }}`

            **Deployments**:
            - ✅ Apptainer: `borg:/runtime/containers/rfd3.sif`
            - ✅ Modal: `foundry-rfd3`

            This PR updates the workflow registry with the latest container metadata.
```

### Workflow 2: Database Synchronization (Optional - Future)

**File**: `.github/workflows/sync-databases.yml` (not implemented yet)

This optional workflow can automate database updates:

```yaml
name: Sync Databases

on:
  workflow_dispatch:  # Manual trigger only

env:
  BORG_HOST: borg
  BORG_USER: arielbs10

jobs:
  sync-pdb:
    name: Sync PDB Database
    runs-on: self-hosted  # On borg
    timeout-minutes: 120

    steps:
      - name: Update PDB mirror on borg
        run: |
          cd /runtime/databases/foundry/pdb
          # Run rsync update from RCSB
          # This is typically managed by a separate script
          echo "PDB mirror update would run here"

      - name: Upload PDB subset to Modal
        run: |
          # Create tarball of essential PDB files
          # Upload to Modal volume
          echo "Modal PDB upload would run here"

  sync-ccd:
    name: Sync CCD Database
    runs-on: self-hosted
    timeout-minutes: 30

    steps:
      - name: Update CCD mirror on borg
        run: |
          cd /runtime/databases/foundry/ccd
          # Update CCD database
          echo "CCD mirror update would run here"

      - name: Upload CCD to Modal
        run: |
          # Upload full CCD to Modal volume
          echo "Modal CCD upload would run here"
```

## Self-Hosted Runner Setup

For deploying to borg, you need a GitHub Actions self-hosted runner on the borg server.

### Setup Instructions

1. **On borg server**:
```bash
# Create runner directory
mkdir -p /runtime/github-runner
cd /runtime/github-runner

# Download and configure runner
# (Follow GitHub's self-hosted runner setup instructions)
# Settings > Actions > Runners > New self-hosted runner

# Install as a service
sudo ./svc.sh install
sudo ./svc.sh start
```

2. **Runner configuration**:
   - **Labels**: `self-hosted`, `linux`, `borg`, `apptainer`
   - **Work directory**: `/runtime/github-runner/_work`
   - **User**: `arielbs10` (has access to /runtime/)

3. **Required permissions**:
   - Read/write access to `/runtime/containers/`
   - Read access to `/runtime/databases/foundry/`
   - Apptainer build permissions (--fakeroot)

## Secrets Configuration

Add these secrets to your GitHub repository:

### Repository Secrets
- `MODAL_TOKEN_ID`: Modal authentication token ID
- `MODAL_TOKEN_SECRET`: Modal authentication token secret
- `WORKFLOW_REPO_TOKEN`: GitHub PAT with write access to workflow repo

### Self-hosted Runner Secrets
- Runner has direct access to borg filesystem
- No SSH credentials needed when runner is on borg

## Scaling to Additional Models

To add a new model (e.g., MPNN, RF3):

1. **Create deployment configs**:
```bash
foundry/
├── deployment/
    ├── apptainer/
    │   └── mpnn/
    │       ├── Containerfile
    │       ├── build.sh
    │       ├── validate.sh
    │       ├── run_test.sh
    │       └── validate_outputs.sh
    └── modal/
        └── mpnn/
            └── app.py
```

2. **Copy and adapt workflow**:
```bash
cp .github/workflows/deploy-rfd3.yml .github/workflows/deploy-mpnn.yml
# Update MODEL_NAME: mpnn
# Update paths and test configurations
```

3. **Commit and push**:
```bash
git add deployment/ .github/workflows/
git commit -m "Add MPNN deployment configs"
git push
```

4. **CI/CD automatically**:
   - Builds MPNN container
   - Deploys to borg at `/runtime/containers/mpnn.sif`
   - Deploys Modal app
   - Updates workflow registry

## Manual Deployment (Fallback)

If CI/CD is unavailable, deploy manually:

### Apptainer (Borg)
```bash
# SSH to borg
ssh arielbs10@borg

# Pull latest code
cd /runtime/repos/foundry
git pull

# Build container
cd deployment/apptainer/rfd3
./build.sh

# Validate and test
./validate.sh
./run_test.sh
```

### Modal (Cloud)
```bash
# Local machine
cd foundry/deployment/modal/rfd3

# Deploy to Modal
modal deploy app.py

# Test deployment
modal run app.py::test_inference
```

## Monitoring and Alerts

### Container Health Checks
- **Validation tests**: Run automatically on every build
- **Inference tests**: num=2 test ensures GPU inference works
- **Output validation**: Biotite structure validation ensures quality

### Alerts
Configure GitHub Actions to notify on:
- Build failures
- Validation failures
- Deployment failures

Add to workflow:
```yaml
- name: Notify on failure
  if: failure()
  uses: 8398a7/action-slack@v3
  with:
    status: ${{ job.status }}
    text: 'RFD3 deployment failed!'
    webhook_url: ${{ secrets.SLACK_WEBHOOK }}
```

## Database Management

### Borg Databases
- **Location**: `/runtime/databases/foundry/`
- **PDB mirror**: Full RCSB PDB mirror (~100GB+)
- **CCD mirror**: Chemical Component Dictionary (~500MB)
- **Update frequency**: Daily via cron or GitHub Actions

### Modal Databases
- **Storage**: Modal volumes (persistent across function calls)
- **PDB subset**: Only essential files for common workflows (~10GB)
- **CCD mirror**: Full CCD mirror (~500MB)
- **Upload strategy**: Tarball transfer from borg, extract to volume

### Initial Setup
```bash
# One-time: Create Modal volumes
modal volume create foundry-pdb
modal volume create foundry-ccd

# Upload databases
# (Use script: workflow/scripts/upload_databases_to_modal.py)
```

## Version Tracking

### Container Versioning
- **Tag**: Git commit SHA (e.g., `a493b31`)
- **Metadata**: Stored in workflow registry JSON
- **Rollback**: Keep previous 3 container versions on borg

### Modal Versioning
- Modal automatically versions deployments
- Access previous versions: `modal app ls --all`

## Cost Optimization

### Apptainer (Borg)
- **Cost**: Fixed (HPC infrastructure)
- **Optimization**: Share databases across all containers

### Modal
- **Cost**: Pay-per-use (GPU time + storage)
- **Optimizations**:
  - Checkpoint in image → faster cold starts
  - Databases in volumes → no repeated downloads
  - Use cheaper GPUs for testing (L4: $1.04/hr vs A100: $4.10/hr)
  - Scale to zero when not in use

## Troubleshooting

### Build Failures
- **Python version mismatch**: Ensure Containerfile uses Python 3.12+
- **Conda TOS**: Use venv instead of Miniconda
- **Interactive prompts**: Set `DEBIAN_FRONTEND=noninteractive`
- **PPA issues**: Run `apt-get update` after adding deadsnakes PPA

### Deployment Failures
- **SSH timeout**: Check GitHub runner connectivity to borg
- **Permission denied**: Verify runner user has write access to /runtime/
- **Modal auth failure**: Check Modal token secrets are current

### Validation Failures
- **GPU not detected**: Ensure `--nv` flag in apptainer exec
- **Database not found**: Verify bind mounts in run_test.sh
- **Import errors**: Check that all dependencies installed in container

## Future Enhancements

1. **Multi-platform builds**: Build for both x86_64 and ARM64
2. **Distributed testing**: Run validation tests across multiple GPUs
3. **Performance benchmarking**: Track inference speed over time
4. **Automated rollback**: Revert to previous container on test failure
5. **Blue-green deployments**: Zero-downtime Modal updates

## Summary

This CI/CD pipeline enables:
- ✅ **Automated builds** on every model update
- ✅ **Dual-platform deployment** (Apptainer + Modal)
- ✅ **Comprehensive testing** before production deployment
- ✅ **Centralized registry** in workflow repo
- ✅ **Easy scaling** to new models (copy workflow, update MODEL_NAME)
- ✅ **Cost optimization** through shared databases and efficient caching

**Next Steps**:
1. Set up self-hosted runner on borg
2. Configure GitHub secrets (Modal tokens, workflow PAT)
3. Create initial `.github/workflows/deploy-rfd3.yml`
4. Test with manual workflow dispatch
5. Enable automatic triggers on model updates
