#!/usr/bin/env bash
set -e

# --------------------------------------------------
# Usage
# --------------------------------------------------
# ./copy_to_circuitops.sh <RUN_NAME> <DESIGN_NAME> <CONTAINER_ID>

RUN_NAME=$1
DESIGN_NAME=$2
CONTAINER=$3

if [ -z "$RUN_NAME" ] || [ -z "$DESIGN_NAME" ] || [ -z "$CONTAINER" ]; then
    echo "Usage: $0 <RUN_NAME> <DESIGN_NAME> <CONTAINER_ID>"
    exit 1
fi

BASE_DIR=$(pwd)
RUN_DIR="$BASE_DIR/runs/$RUN_NAME/final"

echo "======================================================"
echo " LibreLane → CircuitOps Transfer"
echo " Run        : $RUN_NAME"
echo " Design     : $DESIGN_NAME"
echo " Container  : $CONTAINER"
echo "======================================================"

# --------------------------------------------------
# Locate files
# --------------------------------------------------
echo ""
echo "Searching for final files..."

DEF=$(find "$RUN_DIR" -type f -name "*.def" | head -n 1)
VERILOG=$(find "$RUN_DIR" -type f -name "*.v" | head -n 1)
SDC=$(find "$RUN_DIR" -type f -name "*.sdc" | head -n 1)

# SPEF special handling (nom corner)
SPEF=$(find "$RUN_DIR/spef/nom" -type f -name "*.spef" 2>/dev/null | head -n 1)

# fallback if nom doesn't exist
if [ -z "$SPEF" ]; then
    SPEF=$(find "$RUN_DIR" -type f -name "*.spef" | head -n 1)
fi

echo " Found:"
echo "   DEF     : $DEF"
echo "   SPEF    : $SPEF"
echo "   VERILOG : $VERILOG"
echo "   SDC     : $SDC"

# --------------------------------------------------
# Validate files exist
# --------------------------------------------------
for f in "$DEF" "$SPEF" "$VERILOG" "$SDC"; do
    if [ ! -f "$f" ]; then
        echo "ERROR: Missing file: $f"
        exit 1
    fi
done

# --------------------------------------------------
# Temp workspace
# --------------------------------------------------
TMP_DIR=$(mktemp -d)

echo ""
echo "Preparing files (renaming to CircuitOps format)..."

cp "$DEF"     "$TMP_DIR/6_final.def"
cp "$SPEF"    "$TMP_DIR/6_final.spef"
cp "$VERILOG" "$TMP_DIR/6_final.v"
cp "$SDC"     "$TMP_DIR/6_final.sdc"

# --------------------------------------------------
# Compress files
# --------------------------------------------------
echo " Compressing..."

gzip -f "$TMP_DIR/6_final.def"
gzip -f "$TMP_DIR/6_final.spef"
gzip -f "$TMP_DIR/6_final.v"
gzip -f "$TMP_DIR/6_final.sdc"

# --------------------------------------------------
# Destination in Docker container
# --------------------------------------------------
DEST="/app/CircuitOps/designs/sky130hd/${DESIGN_NAME}"

echo ""
echo "Creating destination in container:"
echo "   $DEST"

docker exec "$CONTAINER" mkdir -p "$DEST"

# --------------------------------------------------
# Copy files into container
# --------------------------------------------------
echo "Copying files into container..."

docker cp "$TMP_DIR/6_final.def.gz"  "$CONTAINER:$DEST/"
docker cp "$TMP_DIR/6_final.spef.gz" "$CONTAINER:$DEST/"
docker cp "$TMP_DIR/6_final.v.gz"    "$CONTAINER:$DEST/"
docker cp "$TMP_DIR/6_final.sdc.gz"  "$CONTAINER:$DEST/"

# --------------------------------------------------
# Done
# --------------------------------------------------
echo ""
echo " SUCCESS!"
echo " Files installed in:"
echo "   $DEST"
echo ""
echo " Contents:"
echo "   6_final.def.gz"
echo "   6_final.spef.gz"
echo "   6_final.v.gz"
echo "   6_final.sdc.gz"
echo "======================================================"

# cleanup
rm -rf "$TMP_DIR"
