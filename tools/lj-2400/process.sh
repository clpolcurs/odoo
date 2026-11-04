#!/bin/bash
# process.sh NN [--apply]: one topic from its transcription to Odoo, with a short summary.
# Refreshes the vocabulary snapshot, converts data/raw/topicNN.json, lists the readings Sudachi reads differently,
# then runs apply_topic.py (a dry run unless --apply). Needs LJ_2400_DATA (or data/) and the lj-readings uv project.
set -euo pipefail
cd "$(dirname "$0")"
DATA=${LJ_2400_DATA:-$PWD/data}
NN=$1; shift || true
export LJ_2400_DATA=$DATA
env -u LJ_API_KEY python3 -I fetch_all.py /vocabularies "$DATA/vocab_all.json" >/dev/null
uv run --quiet --no-project --with pykakasi python -I convert.py "$DATA/raw/topic$NN.json" "$DATA/out/topic$NN.json"
echo "--- readings Sudachi reads differently:"
(cd ../lj-readings && uv run --quiet --frozen python ../lj-2400/check_readings.py "$DATA/raw/topic$NN.json" 2>/dev/null) || true
echo "--- write:"
(cd ../lj-readings && env -u LJ_API_KEY uv run --quiet --frozen python ../lj-2400/apply_topic.py "$DATA/out/topic$NN.json" "$@" 2>&1 \
  | grep -v "^  #" | grep -v "UV_NATIVE")
