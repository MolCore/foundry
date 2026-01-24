#!/bin/bash
#
# Build RFD3 Apptainer container on borg server
# Usage: ./build.sh [--force]
#

set -e

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
CONTAINER_NAME="rfd3"
CONTAINER_FILE="${SCRIPT_DIR}/Containerfile"
OUTPUT_SIF="/runtime/containers/${CONTAINER_NAME}.sif"

echo "========================================="
echo "RFD3 Apptainer Container Build"
echo "========================================="
echo ""

# Check if running on borg
HOSTNAME=$(hostname)
if [[ "$HOSTNAME" != *"borg"* ]]; then
    echo "⚠️  Warning: Expected to run on borg server"
    echo "   Current hostname: $HOSTNAME"
    read -p "   Continue anyway? [y/N] " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        echo "Aborted."
        exit 1
    fi
fi

# Check if Containerfile exists
if [[ ! -f "$CONTAINER_FILE" ]]; then
    echo "❌ Error: Containerfile not found: $CONTAINER_FILE"
    exit 1
fi
echo "✓ Found Containerfile: $CONTAINER_FILE"

# Check if output directory exists
OUTPUT_DIR=$(dirname "$OUTPUT_SIF")
if [[ ! -d "$OUTPUT_DIR" ]]; then
    echo "⚠️  Output directory does not exist: $OUTPUT_DIR"
    read -p "   Create it? [y/N] " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        mkdir -p "$OUTPUT_DIR"
        echo "✓ Created directory: $OUTPUT_DIR"
    else
        echo "Aborted."
        exit 1
    fi
fi

# Check if container already exists
if [[ -f "$OUTPUT_SIF" ]]; then
    if [[ "$1" == "--force" ]]; then
        echo "⚠️  Container exists. Removing old version (--force flag)"
        rm -f "$OUTPUT_SIF"
    else
        echo "⚠️  Container already exists: $OUTPUT_SIF"
        echo "   Size: $(du -h "$OUTPUT_SIF" | cut -f1)"
        echo "   Modified: $(stat -c %y "$OUTPUT_SIF" 2>/dev/null || stat -f %Sm "$OUTPUT_SIF" 2>/dev/null)"
        echo ""
        echo "Use --force to rebuild, or delete manually:"
        echo "  rm $OUTPUT_SIF"
        exit 0
    fi
fi

# Build container
echo ""
echo "========================================="
echo "Building container..."
echo "========================================="
echo "  Definition file: $CONTAINER_FILE"
echo "  Output file: $OUTPUT_SIF"
echo "  Build method: --fakeroot (no root required)"
echo ""

START_TIME=$(date +%s)

apptainer build --fakeroot "$OUTPUT_SIF" "$CONTAINER_FILE"

END_TIME=$(date +%s)
BUILD_TIME=$((END_TIME - START_TIME))

# Verify build success
echo ""
echo "========================================="
if [[ -f "$OUTPUT_SIF" ]]; then
    echo "✅ Build successful!"
    echo "========================================="
    echo ""
    echo "Container details:"
    echo "  Location: $OUTPUT_SIF"
    echo "  Size: $(du -h "$OUTPUT_SIF" | cut -f1)"
    echo "  Build time: ${BUILD_TIME}s ($(($BUILD_TIME / 60))m $(($BUILD_TIME % 60))s)"
    echo ""
    echo "Next steps:"
    echo "  1. Validate container: ./validate.sh"
    echo "  2. Run test: ./run_test.sh"
    echo ""
else
    echo "❌ Build failed!"
    echo "========================================="
    echo ""
    echo "Container file not created. Check error messages above."
    exit 1
fi
