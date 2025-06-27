#!/usr/bin/env bash
# -----------------------------------------------------------------------------
# UGLYCASH – Full analysis pipeline
# -----------------------------------------------------------------------------
# Generates a tagged Olympus transactions file (ATM vs POS) and then runs the
# user segmentation + metrics pipeline so outputs are ready for the P&L
# dashboard.  Adjust the variables below if your filenames change.
# -----------------------------------------------------------------------------
# Usage:
#   ./run_full_analysis.sh               # uses default filenames
#   ./run_full_analysis.sh tribe_new.csv # custom tribe CSV
#
# Requirements:
#   • preprocess_card_type_atm_first.py
#   • user_segmentation_analyzer.py
#   • Bash shell + Python 3 with required libs (see requirements.txt)
# -----------------------------------------------------------------------------
set -euo pipefail

# ---- Configurable filenames --------------------------------------------------
OLYMPUS_FILE="olympus_all_txs.csv"               # raw Olympus export
TRIBE_FILE="${1:-tribe.csv}"                    # updated Tribe export (arg1)
RULES_FILE="Movimientos_por_tipo_y_side___completa_efecto.csv"  # balance rules
TAGGED_FILE="olympus_all_txs_tagged_atm.csv"    # output with ATM/POS tags
OUTPUT_DIR="segmentation_outputs"               # analyzer outputs (read by dashboard)

# ---- Step 1: tag ATM vs POS --------------------------------------------------
python preprocess_card_type_atm_first.py \
    --olympus "$OLYMPUS_FILE" \
    --tribe "$TRIBE_FILE" \
    --output "$TAGGED_FILE"

# ---- Step 2: run segmentation & metrics -------------------------------------
python user_segmentation_analyzer.py \
    --transactions "$TAGGED_FILE" \
    --rules "$RULES_FILE" \
    --outdir "$OUTPUT_DIR"

echo -e "\n✓ Pipeline finished. Dashboard can now read data from: $OUTPUT_DIR" 