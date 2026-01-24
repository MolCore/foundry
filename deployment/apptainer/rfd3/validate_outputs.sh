#!/bin/bash
#
# Validate RFD3 output structures
# Usage: ./validate_outputs.sh <output_directory>
#

set -e

OUTPUT_DIR="$1"
CONTAINER_SIF="/runtime/containers/rfd3.sif"

if [[ -z "$OUTPUT_DIR" ]] || [[ ! -d "$OUTPUT_DIR" ]]; then
    echo "Usage: $0 <output_directory>"
    echo ""
    echo "Example:"
    echo "  $0 ./outputs/rfd3_test_20260124_120000"
    exit 1
fi

echo "========================================="
echo "RFD3 Output Validation"
echo "========================================="
echo "Directory: $OUTPUT_DIR"
echo ""

# Count files
echo "[1/4] Counting output files..."
CIF_COUNT=$(find "$OUTPUT_DIR" -name "*.cif*" -type f | wc -l)
JSON_COUNT=$(find "$OUTPUT_DIR" -name "*.json" -type f | wc -l)

echo "  CIF structures: $CIF_COUNT"
echo "  JSON metadata: $JSON_COUNT"

if [[ $CIF_COUNT -eq 0 ]]; then
    echo ""
    echo "❌ ERROR: No CIF files found in $OUTPUT_DIR"
    exit 1
fi

if [[ $CIF_COUNT -ge 2 ]]; then
    echo "  ✓ Expected ≥2 structures, found $CIF_COUNT"
else
    echo "  ⚠️  WARNING: Expected ≥2 structures, found $CIF_COUNT"
fi
echo ""

# Validate structure format
echo "[2/4] Validating structure format..."
VALID_COUNT=0
TOTAL_COUNT=0

for CIF_FILE in "$OUTPUT_DIR"/*.cif*; do
    if [[ -f "$CIF_FILE" ]]; then
        TOTAL_COUNT=$((TOTAL_COUNT + 1))
        BASENAME=$(basename "$CIF_FILE")

        # Check file size
        FILE_SIZE=$(stat -c%s "$CIF_FILE" 2>/dev/null || stat -f%z "$CIF_FILE" 2>/dev/null)
        if [[ $FILE_SIZE -eq 0 ]]; then
            echo "  ✗ $BASENAME - EMPTY FILE"
            continue
        fi

        # Validate with biotite (if available in container)
        apptainer exec "$CONTAINER_SIF" python -c "
import sys
import gzip
from pathlib import Path

cif_path = Path('$CIF_FILE')

# Check if biotite is available
try:
    from biotite.structure.io import load_structure
except ImportError:
    # Fallback: just check if file is readable
    if cif_path.exists() and cif_path.stat().st_size > 0:
        # Handle gzipped files
        if str(cif_path).endswith('.gz'):
            with gzip.open(cif_path, 'rt') as f:
                content = f.read()
        else:
            content = cif_path.read_text()

        if 'ATOM' in content or '_atom_site' in content:
            print('✓ $BASENAME - Valid CIF format (basic check)')
            sys.exit(0)
        else:
            print('✗ $BASENAME - Invalid CIF format')
            sys.exit(1)
    sys.exit(1)

# Full validation with biotite
try:
    # Decompress if needed
    if str(cif_path).endswith('.gz'):
        import tempfile
        with gzip.open(cif_path, 'rb') as gz_file:
            with tempfile.NamedTemporaryFile(mode='wb', suffix='.cif', delete=False) as tmp_file:
                tmp_file.write(gz_file.read())
                tmp_path = tmp_file.name
        structure = load_structure(tmp_path)
        Path(tmp_path).unlink()  # Clean up temp file
    else:
        structure = load_structure(str(cif_path))

    n_atoms = structure.array_length()
    n_residues = len(set(structure.res_id))

    # Basic sanity checks
    if n_atoms == 0:
        print('✗ $BASENAME - No atoms')
        sys.exit(1)

    if n_residues == 0:
        print('✗ $BASENAME - No residues')
        sys.exit(1)

    print(f'✓ $BASENAME - {n_atoms} atoms, {n_residues} residues')
    sys.exit(0)

except Exception as e:
    print(f'✗ $BASENAME - Failed to load: {str(e)[:50]}')
    sys.exit(1)
" && VALID_COUNT=$((VALID_COUNT + 1))
    fi
done

echo ""
echo "  Validation summary: $VALID_COUNT/$TOTAL_COUNT structures valid"

if [[ $VALID_COUNT -eq $TOTAL_COUNT ]]; then
    echo "  ✓ All structures valid"
elif [[ $VALID_COUNT -eq 0 ]]; then
    echo "  ❌ ERROR: No valid structures found"
    exit 1
else
    echo "  ⚠️  WARNING: Some structures failed validation"
fi
echo ""

# Check JSON metadata
echo "[3/4] Checking JSON metadata..."
JSON_VALID=0

for JSON_FILE in "$OUTPUT_DIR"/*.json; do
    if [[ -f "$JSON_FILE" ]]; then
        BASENAME=$(basename "$JSON_FILE")

        # Check if valid JSON
        if python3 -m json.tool "$JSON_FILE" > /dev/null 2>&1; then
            JSON_VALID=$((JSON_VALID + 1))

            # Try to extract key fields
            apptainer exec "$CONTAINER_SIF" python -c "
import json
import sys
from pathlib import Path

json_path = Path('$JSON_FILE')
data = json.loads(json_path.read_text())

# Look for common RFD3 output fields
fields_found = []
if 'confidence' in data:
    fields_found.append(f\"confidence={data['confidence']:.3f}\")
if 'plddt' in data:
    fields_found.append(f\"pLDDT={data['plddt']:.2f}\")
if 'ptm' in data:
    fields_found.append(f\"pTM={data['ptm']:.3f}\")

if fields_found:
    print('  ✓ $BASENAME -', ', '.join(fields_found))
else:
    print('  ✓ $BASENAME - Valid JSON (no quality metrics found)')
" || echo "  ✓ $BASENAME - Valid JSON"
        else
            echo "  ✗ $BASENAME - Invalid JSON"
        fi
    fi
done

if [[ $JSON_VALID -gt 0 ]]; then
    echo "  ✓ Found $JSON_VALID valid JSON metadata files"
fi
echo ""

# File size statistics
echo "[4/4] File size statistics..."
TOTAL_SIZE=0
MIN_SIZE=999999999
MAX_SIZE=0
COUNT=0

for CIF_FILE in "$OUTPUT_DIR"/*.cif*; do
    if [[ -f "$CIF_FILE" ]]; then
        FILE_SIZE=$(stat -c%s "$CIF_FILE" 2>/dev/null || stat -f%z "$CIF_FILE" 2>/dev/null)
        TOTAL_SIZE=$((TOTAL_SIZE + FILE_SIZE))
        COUNT=$((COUNT + 1))

        if [[ $FILE_SIZE -lt $MIN_SIZE ]]; then
            MIN_SIZE=$FILE_SIZE
        fi
        if [[ $FILE_SIZE -gt $MAX_SIZE ]]; then
            MAX_SIZE=$FILE_SIZE
        fi
    fi
done

if [[ $COUNT -gt 0 ]]; then
    AVG_SIZE=$((TOTAL_SIZE / COUNT))
    echo "  Total size: $((TOTAL_SIZE / 1024)) KB"
    echo "  Average size: $((AVG_SIZE / 1024)) KB per structure"
    echo "  Size range: $((MIN_SIZE / 1024)) KB - $((MAX_SIZE / 1024)) KB"
fi
echo ""

# Final summary
echo "========================================="
echo "Validation Summary"
echo "========================================="
echo "✓ Output directory: $OUTPUT_DIR"
echo "✓ Total structures: $CIF_COUNT"
echo "✓ Valid structures: $VALID_COUNT"
echo "✓ JSON metadata files: $JSON_VALID"

if [[ $VALID_COUNT -ge 2 ]] && [[ $VALID_COUNT -eq $CIF_COUNT ]]; then
    echo ""
    echo "✅ All validations passed!"
    echo ""
    echo "Borg testing complete. Ready for Modal implementation."
else
    echo ""
    echo "⚠️  Some validations failed. Review output above."
fi
echo ""
