# CI/CD Setup Guide

## Quick Start

This guide walks you through setting up the automated CI/CD pipeline for RFD3 container deployment.

**Time required**: ~30 minutes
**Prerequisites**: Admin access to GitHub repo and borg server

## Overview

The CI/CD pipeline automatically:
1. 🏗️  Builds Apptainer container on borg when code changes
2. ✅ Validates container and runs test inference
3. 📦 Deploys to `/runtime/containers/rfd3_latest.sif` with versioning
4. 🗃️  Archives previous version to `/runtime/containers/legacy/`
5. 📝 Updates workflow repository registry
6. 🧹 Cleans up old versions (keeps 5 most recent)

## Versioning Strategy

Each container deployment creates:
- **Current**: `/runtime/containers/rfd3_latest.sif` (always points to latest)
- **Metadata**: `/runtime/containers/rfd3.json` (UUID, date, reproducibility info)
- **Archive**: `/runtime/containers/legacy/rfd3_<UUID>.sif` (previous versions)

Example:
```
/runtime/containers/
├── rfd3_latest.sif          # Current version (9.2 GB)
├── rfd3.json                # Current metadata
└── legacy/
    ├── rfd3_a1b2c3d4.sif    # Previous version 1
    ├── rfd3_a1b2c3d4.json
    ├── rfd3_e5f6g7h8.sif    # Previous version 2
    └── rfd3_e5f6g7h8.json
```

When a new version deploys:
1. Current `rfd3_latest.sif` → `legacy/rfd3_<old-UUID>.sif`
2. Current `rfd3.json` → `legacy/rfd3_<old-UUID>.json`
3. New container → `rfd3_latest.sif`
4. New metadata → `rfd3.json`

## Step 1: Setup GitHub Runner on Borg

The runner allows GitHub Actions to execute builds directly on borg.

### 1.1 Run Setup Script

```bash
# SSH to borg
ssh arielbs10@borg

# Navigate to deployment directory
cd /runtime/repos/foundry/deployment/apptainer/rfd3

# Run setup script
./setup_runner.sh
```

This creates `/runtime/github-runner/` and downloads the runner software.

### 1.2 Get Registration Token

1. Go to: https://github.com/MolCore/foundry/settings/actions/runners/new
2. Select **Linux** as operating system
3. Copy the registration token (starts with `AAAA...`)

### 1.3 Configure Runner

```bash
cd /runtime/github-runner

./config.sh \
  --url https://github.com/MolCore/foundry \
  --token YOUR_REGISTRATION_TOKEN_HERE \
  --name borg-runner \
  --labels self-hosted,linux,borg,apptainer,x64 \
  --work /runtime/github-runner/_work \
  --unattended
```

### 1.4 Install as Service

```bash
# Install service (requires sudo)
sudo ./svc.sh install arielbs10

# Start service
sudo ./svc.sh start

# Verify status
sudo ./svc.sh status
```

Expected output:
```
● actions.runner.MolCore-foundry.borg-runner.service - GitHub Actions Runner
   Active: active (running)
```

### 1.5 Verify in GitHub

Visit: https://github.com/MolCore/foundry/settings/actions/runners

You should see:
- **borg-runner** status: **Idle** ✅ (green)
- Labels: `self-hosted`, `linux`, `borg`, `apptainer`, `x64`

## Step 2: Configure GitHub Secrets

### 2.1 Required Secrets

Go to: https://github.com/MolCore/foundry/settings/secrets/actions

Add these repository secrets:

| Secret Name | Description | How to Get |
|------------|-------------|------------|
| `MODAL_TOKEN_ID` | Modal auth token ID | https://modal.com/settings/tokens |
| `MODAL_TOKEN_SECRET` | Modal auth token secret | https://modal.com/settings/tokens |
| `WORKFLOW_REPO_TOKEN` | GitHub PAT for workflow repo | See below |

### 2.2 Create WORKFLOW_REPO_TOKEN

This token allows the CI/CD to create PRs in the workflow registry repo.

1. Go to: https://github.com/settings/tokens/new
2. **Note**: `foundry-cicd-workflow-updates`
3. **Expiration**: 1 year (or no expiration)
4. **Scopes**: Select:
   - ✅ `repo` (Full control of private repositories)
   - ✅ `workflow` (Update GitHub Action workflows)
5. Click **Generate token**
6. Copy token and add to foundry repo secrets as `WORKFLOW_REPO_TOKEN`

### 2.3 Modal Tokens (Optional - for future Modal deployment)

1. Go to: https://modal.com/settings/tokens
2. Click **Create new token**
3. Name: `foundry-cicd`
4. Copy both:
   - Token ID → `MODAL_TOKEN_ID`
   - Token Secret → `MODAL_TOKEN_SECRET`

## Step 3: Test the Pipeline

### 3.1 Manual Trigger (Recommended First Test)

1. Go to: https://github.com/MolCore/foundry/actions/workflows/deploy-rfd3.yml
2. Click **Run workflow**
3. Select branch: `production`
4. Check **Force rebuild**: `true` (optional)
5. Click **Run workflow**

### 3.2 Monitor Build

Watch the workflow run at:
https://github.com/MolCore/foundry/actions

Expected stages:
1. ✅ **Build Apptainer Container** (~10 min)
   - Checkout code
   - Build container
   - Validate infrastructure
   - Run test inference
   - Deploy to versioned containers
2. ✅ **Update Workflow Registry** (~1 min)
   - Create PR in workflow repo
3. ⏸️  **Deploy Modal App** (skipped - not implemented yet)

### 3.3 Verify Deployment

```bash
# SSH to borg
ssh arielbs10@borg

# Check current container
ls -lh /runtime/containers/rfd3_latest.sif
cat /runtime/containers/rfd3.json

# Check legacy archives
ls -lh /runtime/containers/legacy/
```

Expected:
- `rfd3_latest.sif` - new container with today's timestamp
- `rfd3.json` - metadata with UUID and build info
- `legacy/` - previous version archived (if this wasn't first build)

### 3.4 Test Container

```bash
# Quick validation
apptainer exec --nv /runtime/containers/rfd3_latest.sif rfd3 --help

# Run inference test
cd /runtime/repos/foundry/deployment/apptainer/rfd3
./run_test.sh
```

## Step 4: Enable Automatic Triggers

Once manual test succeeds, enable automatic builds.

### 4.1 Automatic Triggers

The workflow automatically runs on:

1. **Code push to production branch**:
   - Changes to `models/rfd3/**`
   - Changes to `deployment/apptainer/rfd3/**`
   - Changes to `deployment/modal/rfd3/**`
   - Changes to `.github/workflows/deploy-rfd3.yml`

2. **Weekly scheduled builds** (Sundays 2 AM UTC):
   - Picks up dependency updates
   - Validates container still builds
   - Cleans up old legacy versions

3. **Manual dispatch** (as tested above):
   - On-demand rebuilds
   - Testing changes

### 4.2 Test Automatic Trigger

Make a small change to trigger build:

```bash
# Edit README
echo "# RFD3 v$(date +%Y%m%d)" >> deployment/apptainer/rfd3/README.md

# Commit and push
git add deployment/apptainer/rfd3/README.md
git commit -m "Trigger CI/CD test"
git push
```

Watch: https://github.com/MolCore/foundry/actions

## Step 5: Workflow Registry Integration

After each successful build, the CI/CD creates a PR in the workflow repo.

### 5.1 Review and Merge PR

1. Go to: https://github.com/MolCore/workflow/pulls
2. Find PR: **"Update rfd3 container to <commit>"**
3. Review changes in `containers/registry/rfd3.json`
4. Merge PR

### 5.2 Registry Format

The registry JSON contains:
```json
{
  "model": "rfd3",
  "version": {
    "uuid": "a1b2c3d4-...",
    "git_commit": "abc123...",
    "build_date": "2026-01-26T..."
  },
  "container": {
    "path": "/runtime/containers/rfd3_latest.sif",
    "size": 9123456789,
    "hash": "sha256:..."
  },
  "platforms": {
    "apptainer": {
      "available": true,
      "location": "borg:/runtime/containers/rfd3_latest.sif"
    }
  }
}
```

Workflows can read this to discover available containers and versions.

## Troubleshooting

### Issue: Runner shows offline

**Symptom**: Runner status is "Offline" in GitHub

**Solution**:
```bash
ssh arielbs10@borg
cd /runtime/github-runner
sudo ./svc.sh status
sudo ./svc.sh restart
```

### Issue: Permission denied during build

**Symptom**: Build fails with "Permission denied" to `/runtime/`

**Solution**:
```bash
# Check runner user
ps aux | grep Runner.Listener

# Ensure runner user has write access
sudo chown -R arielbs10:arielbs10 /runtime/containers
sudo chmod 755 /runtime/containers
```

### Issue: Workflow triggered but no build

**Symptom**: Workflow shows in Actions but no jobs run

**Solution**: Check path filters. Workflow only runs on changes to:
- `models/rfd3/**`
- `deployment/apptainer/rfd3/**`
- `.github/workflows/deploy-rfd3.yml`

### Issue: Container validation fails

**Symptom**: Build succeeds but validation fails

**Solution**:
```bash
# Check databases are mounted
ls /runtime/databases/foundry/pdb/
ls /runtime/databases/foundry/ccd/

# Run validation manually
cd /runtime/repos/foundry/deployment/apptainer/rfd3
./validate.sh
```

### Issue: GPU not detected in CI/CD

**Symptom**: Validation step fails with "CUDA not available"

**Solution**: Ensure runner can access GPU:
```bash
# Test GPU access
nvidia-smi

# Verify apptainer can see GPU
apptainer exec --nv /runtime/containers/rfd3_latest.sif nvidia-smi
```

## Rollback Procedure

If a new container has issues, rollback to previous version:

### Option 1: Restore from Legacy

```bash
# List legacy versions
ls -lh /runtime/containers/legacy/rfd3_*.sif

# Check metadata to find desired version
cat /runtime/containers/legacy/rfd3_<UUID>.json

# Restore previous version
cd /runtime/containers
mv rfd3_latest.sif rfd3_broken_$(date +%Y%m%d).sif
cp legacy/rfd3_<UUID>.sif rfd3_latest.sif
cp legacy/rfd3_<UUID>.json rfd3.json
```

### Option 2: Re-run Previous Build

```bash
# Find previous successful commit
git log --oneline deployment/apptainer/rfd3/

# Checkout previous version
git checkout <previous-commit> -- deployment/apptainer/rfd3/

# Trigger rebuild
git commit -m "Rollback to previous version"
git push
```

## Maintenance

### Weekly Tasks (Automated)

The workflow automatically runs weekly (Sundays 2 AM UTC) to:
- Rebuild container with latest dependencies
- Test container still works
- Clean up old legacy versions (keeps 5 most recent)

### Manual Cleanup

If you need to manually clean up legacy versions:

```bash
cd /runtime/containers/legacy

# List versions by date
ls -lht rfd3_*.sif

# Remove specific version
rm rfd3_<UUID>.sif rfd3_<UUID>.json

# Or keep only newest N versions
ls -t rfd3_*.sif | tail -n +6 | xargs rm -f
```

### Monitor Disk Usage

```bash
# Check container directory size
du -sh /runtime/containers
du -sh /runtime/containers/legacy

# Check individual containers
du -sh /runtime/containers/rfd3_*.sif
```

## Next Steps

1. ✅ **Complete setup** (Steps 1-3 above)
2. 🔄 **Monitor first automatic build** on next code push
3. 📊 **Set up monitoring** (GitHub Action notifications)
4. 🚀 **Extend to other models** (MPNN, RF3):
   - Copy `deployment/apptainer/rfd3/` → `deployment/apptainer/mpnn/`
   - Copy `.github/workflows/deploy-rfd3.yml` → `deploy-mpnn.yml`
   - Update `MODEL_NAME` in workflow
5. ☁️  **Implement Modal deployment** (currently disabled in workflow)

## Summary

After setup, the CI/CD pipeline:
- ✅ Automatically builds on code changes
- ✅ Validates every build with tests
- ✅ Versions containers with UUID and metadata
- ✅ Archives previous versions for rollback
- ✅ Updates workflow registry
- ✅ Cleans up old versions weekly

**Result**: Fully automated, reliable deployments with complete version history and easy rollback.
