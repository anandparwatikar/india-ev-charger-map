#!/usr/bin/env bash
# Rebuild everything from the raw station list: geo data, cleaned CSVs and index.html.
set -euo pipefail
cd "$(dirname "$0")/scripts"
python3 01_download_sources.py
python3 02_prepare_geo.py
python3 03_clean_stations.py
python3 04_build_map.py
