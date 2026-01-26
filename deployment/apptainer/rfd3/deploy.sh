#!/bin/bash
#
# Deploy RFD3 container to /runtime/containers with versioning
# Handles moving previous version to legacy/ and creating metadata
#
# Usage: ./deploy.sh <container_sif_path> [git_commit_sha]
#

set -e

CONTAINER_SIF="$1"
GIT_COMMIT="${2:-$(git rev-parse HEAD)}"
MODEL_NAME="rfd3"

# Paths
RUNTIME_CONTAINERS="/runtime/containers"
LATEST_SIF="${RUNTIME_CONTAINERS}/${MODEL_NAME}_latest.sif"
LATEST_JSON="${RUNTIME_CONTAINERS}/${MODEL_NAME}.json"
LEGACY_DIR="${RUNTIME_CONTAINERS}/legacy"

if [[ -z "$CONTAINER_SIF" ]]; then
    echo "Usage: $0 <container_sif_path> [git_commit_sha]"
    echo ""
    echo "Example:"
    echo "  $0 /runtime/containers/rfd3.sif a493b31"
    exit 1
fi

if [[ ! -f "$CONTAINER_SIF" ]]; then
    echo "❌ ERROR: Container file not found: $CONTAINER_SIF"
    exit 1
fi

echo "========================================="
echo "RFD3 Container Deployment"
echo "========================================="
echo "Source: $CONTAINER_SIF"
echo "Target: $LATEST_SIF"
echo "Commit: $GIT_COMMIT"
echo ""

# Create directories
mkdir -p "$RUNTIME_CONTAINERS"
mkdir -p "$LEGACY_DIR"

# Generate UUID for this version
VERSION_UUID=$(uuidgen | tr '[:upper:]' '[:lower:]')

# Extract metadata
CONTAINER_SIZE=$(stat -c%s "$CONTAINER_SIF" 2>/dev/null || stat -f%z "$CONTAINER_SIF")
CONTAINER_HASH=$(sha256sum "$CONTAINER_SIF" | cut -d' ' -f1)
BUILD_DATE=$(date -u +"%Y-%m-%dT%H:%M:%SZ")
BUILD_TIMESTAMP=$(date +%s)

# Python version check
PYTHON_VERSION=$(apptainer exec "$CONTAINER_SIF" python --version 2>&1 | awk '{print $2}')

# PyTorch/CUDA check
PYTORCH_INFO=$(apptainer exec "$CONTAINER_SIF" python -c "
import torch
print(f'{torch.__version__}|{torch.cuda.is_available()}|{torch.version.cuda if torch.cuda.is_available() else \"N/A\"}')
" 2>/dev/null || echo "unknown|false|N/A")

PYTORCH_VERSION=$(echo "$PYTORCH_INFO" | cut -d'|' -f1)
CUDA_AVAILABLE=$(echo "$PYTORCH_INFO" | cut -d'|' -f2)
CUDA_VERSION=$(echo "$PYTORCH_INFO" | cut -d'|' -f3)

# Check if previous version exists
if [[ -f "$LATEST_SIF" ]]; then
    echo "Found existing container: $LATEST_SIF"

    # Load previous metadata
    if [[ -f "$LATEST_JSON" ]]; then
        PREV_UUID=$(python3 -c "import json; print(json.load(open('$LATEST_JSON'))['version']['uuid'])" 2>/dev/null || echo "unknown")
        PREV_DATE=$(python3 -c "import json; print(json.load(open('$LATEST_JSON'))['version']['build_date'])" 2>/dev/null || echo "unknown")

        echo "Previous version:"
        echo "  UUID: $PREV_UUID"
        echo "  Date: $PREV_DATE"

        # Archive previous version
        ARCHIVE_SIF="${LEGACY_DIR}/${MODEL_NAME}_${PREV_UUID}.sif"
        ARCHIVE_JSON="${LEGACY_DIR}/${MODEL_NAME}_${PREV_UUID}.json"

        echo ""
        echo "Archiving previous version to legacy/..."
        mv "$LATEST_SIF" "$ARCHIVE_SIF"
        mv "$LATEST_JSON" "$ARCHIVE_JSON"

        echo "✓ Archived: $(basename $ARCHIVE_SIF)"
        echo "✓ Archived: $(basename $ARCHIVE_JSON)"
    else
        echo "⚠️  WARNING: No metadata file found for previous version"
        # Archive without UUID
        ARCHIVE_SIF="${LEGACY_DIR}/${MODEL_NAME}_backup_${BUILD_TIMESTAMP}.sif"
        mv "$LATEST_SIF" "$ARCHIVE_SIF"
        echo "✓ Archived: $(basename $ARCHIVE_SIF)"
    fi
else
    echo "No existing container found (first deployment)"
fi

echo ""
echo "Deploying new version..."

# Copy new container
cp "$CONTAINER_SIF" "$LATEST_SIF"
echo "✓ Deployed: $(basename $LATEST_SIF) ($(numfmt --to=iec-i --suffix=B $CONTAINER_SIZE))"

# Create metadata JSON
cat > "$LATEST_JSON" <<EOF
{
  "model": "$MODEL_NAME",
  "version": {
    "uuid": "$VERSION_UUID",
    "git_commit": "$GIT_COMMIT",
    "build_date": "$BUILD_DATE",
    "build_timestamp": $BUILD_TIMESTAMP
  },
  "container": {
    "path": "$LATEST_SIF",
    "size": $CONTAINER_SIZE,
    "hash": "$CONTAINER_HASH"
  },
  "environment": {
    "python_version": "$PYTHON_VERSION",
    "pytorch_version": "$PYTORCH_VERSION",
    "cuda_available": $CUDA_AVAILABLE,
    "cuda_version": "$CUDA_VERSION"
  },
  "deployment": {
    "deployed_by": "$(whoami)",
    "deployed_from": "$(hostname)",
    "repository": "https://github.com/MolCore/foundry",
    "branch": "$(git rev-parse --abbrev-ref HEAD 2>/dev/null || echo 'unknown')"
  },
  "reproducibility": {
    "containerfile": "deployment/apptainer/rfd3/Containerfile",
    "build_script": "deployment/apptainer/rfd3/build.sh",
    "git_commit": "$GIT_COMMIT",
    "instructions": "To reproduce: git checkout $GIT_COMMIT && cd deployment/apptainer/rfd3 && ./build.sh"
  }
}
EOF

echo "✓ Created metadata: $(basename $LATEST_JSON)"

echo ""
echo "========================================="
echo "Deployment Summary"
echo "========================================="
echo "Model: $MODEL_NAME"
echo "UUID: $VERSION_UUID"
echo "Size: $(numfmt --to=iec-i --suffix=B $CONTAINER_SIZE)"
echo "Hash: ${CONTAINER_HASH:0:16}..."
echo "Python: $PYTHON_VERSION"
echo "PyTorch: $PYTORCH_VERSION (CUDA: $CUDA_VERSION)"
echo ""
echo "Files:"
echo "  $LATEST_SIF"
echo "  $LATEST_JSON"
echo ""

# List legacy versions
LEGACY_COUNT=$(ls -1 "$LEGACY_DIR"/${MODEL_NAME}_*.sif 2>/dev/null | wc -l)
if [[ $LEGACY_COUNT -gt 0 ]]; then
    echo "Legacy versions: $LEGACY_COUNT"
    echo "  Location: $LEGACY_DIR"
    echo ""
    echo "  Recent archives:"
    ls -lht "$LEGACY_DIR"/${MODEL_NAME}_*.sif | head -3 | awk '{print "  - " $9 " (" $5 ", " $6 " " $7 ")"}'
fi

echo ""
echo "✅ Deployment complete!"
echo ""
echo "Usage:"
echo "  apptainer exec --nv $LATEST_SIF rfd3 design --help"
echo ""
