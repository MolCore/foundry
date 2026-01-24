#!/bin/bash
#
# Run RFD3 test inference on borg with num=2 designs
# Usage: ./run_test.sh [config_name]
#

set -e

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
CONTAINER_SIF="/runtime/containers/rfd3.sif"
CONFIG_NAME="${1:-test_num2}"
CONFIG_FILE="${SCRIPT_DIR}/test_configs/${CONFIG_NAME}.json"
OUTPUT_DIR="${SCRIPT_DIR}/outputs/rfd3_test_$(date +%Y%m%d_%H%M%S)"

# Database paths on borg
PDB_MIRROR="/runtime/databases/foundry/pdb"
CCD_MIRROR="/runtime/databases/foundry/ccd"

echo "========================================="
echo "RFD3 Test Run on Borg"
echo "========================================="
echo "Config: $CONFIG_NAME"
echo "Config file: $CONFIG_FILE"
echo "Output dir: $OUTPUT_DIR"
echo "Container: $CONTAINER_SIF"
echo ""

# Check container exists
if [[ ! -f "$CONTAINER_SIF" ]]; then
    echo "❌ ERROR: Container not found: $CONTAINER_SIF"
    echo ""
    echo "Build the container first:"
    echo "  ./build.sh"
    exit 1
fi

# Check config exists
if [[ ! -f "$CONFIG_FILE" ]]; then
    echo "❌ ERROR: Config file not found: $CONFIG_FILE"
    echo ""
    echo "Available configs:"
    ls -1 "${SCRIPT_DIR}/test_configs/"*.json 2>/dev/null || echo "  (none found)"
    exit 1
fi

# Check databases exist
if [[ ! -d "$PDB_MIRROR" ]] || [[ ! -d "$CCD_MIRROR" ]]; then
    echo "❌ ERROR: Database directories not found"
    echo "   PDB: $PDB_MIRROR $(if [[ -d "$PDB_MIRROR" ]]; then echo "✓"; else echo "✗"; fi)"
    echo "   CCD: $CCD_MIRROR $(if [[ -d "$CCD_MIRROR" ]]; then echo "✓"; else echo "✗"; fi)"
    exit 1
fi

# Create output directory
mkdir -p "$OUTPUT_DIR"
echo "✓ Created output directory"
echo ""

# Log GPU info before inference
echo "========================================="
echo "GPU Information"
echo "========================================="
nvidia-smi --query-gpu=index,name,memory.total,memory.free --format=csv,noheader || echo "⚠️  nvidia-smi not available"
echo ""

# Run RFD3 inference
echo "========================================="
echo "Starting RFD3 Inference (num=2 designs)"
echo "========================================="
echo ""

START_TIME=$(date +%s)

apptainer exec --nv \
    --bind "$PDB_MIRROR:/runtime/databases/foundry/pdb:ro" \
    --bind "$CCD_MIRROR:/runtime/databases/foundry/ccd:ro" \
    --bind "${SCRIPT_DIR}/test_configs:/workspace/configs:ro" \
    --bind "$OUTPUT_DIR:/workspace/outputs" \
    --env PDB_MIRROR_PATH=/runtime/databases/foundry/pdb \
    --env CCD_MIRROR_PATH=/runtime/databases/foundry/ccd \
    "$CONTAINER_SIF" \
    rfd3 design \
        out_dir=/workspace/outputs \
        inputs=/workspace/configs/${CONFIG_NAME}.json \
        n_batches=1 \
        diffusion_batch_size=2 \
        skip_existing=False \
        dump_trajectories=False \
        prevalidate_inputs=True

END_TIME=$(date +%s)
INFERENCE_TIME=$((END_TIME - START_TIME))

echo ""
echo "========================================="
echo "RFD3 Inference Complete"
echo "========================================="
echo "Inference time: ${INFERENCE_TIME}s ($(($INFERENCE_TIME / 60))m $(($INFERENCE_TIME % 60))s)"
echo "Output directory: $OUTPUT_DIR"
echo ""

# Check outputs
echo "Checking generated files..."
echo ""

CIF_COUNT=$(find "$OUTPUT_DIR" -name "*.cif*" -type f | wc -l)
JSON_COUNT=$(find "$OUTPUT_DIR" -name "*.json" -type f | wc -l)

echo "Files generated:"
echo "  CIF structures: $CIF_COUNT"
echo "  JSON metadata: $JSON_COUNT"
echo ""

if [[ $CIF_COUNT -ge 2 ]]; then
    echo "✅ Test successful - generated $CIF_COUNT structures (expected ≥2)"
else
    echo "⚠️  WARNING - expected ≥2 structures, got $CIF_COUNT"
fi

# List output files
echo ""
echo "Output files:"
find "$OUTPUT_DIR" -type f | head -20
echo ""

# Show GPU memory after inference
echo "========================================="
echo "GPU Status After Inference"
echo "========================================="
nvidia-smi --query-gpu=index,memory.used,memory.free,utilization.gpu --format=csv,noheader || echo "⚠️  nvidia-smi not available"
echo ""

echo "========================================="
echo "Next Steps"
echo "========================================="
echo "1. Validate outputs:"
echo "   ./validate_outputs.sh \"$OUTPUT_DIR\""
echo ""
echo "2. Inspect structures:"
echo "   ls -lh \"$OUTPUT_DIR\"/*.cif*"
echo ""
echo "3. View metadata:"
echo "   cat \"$OUTPUT_DIR\"/*.json | head -50"
echo ""
