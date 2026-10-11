"""Shared paths and helpers for the build pipeline."""
from pathlib import Path
import math

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "data" / "raw"
PROCESSED = ROOT / "data" / "processed"
GEO = ROOT / "data" / "geo"
DOWNLOADS = GEO / "_downloads"          # large third-party files, not committed
SRC = ROOT / "src"
VENDOR = ROOT / "vendor"

SOURCE_XLSX = RAW / "EV_PCS_Data_29277.xlsx"

# Rough bounding box of India (lon/lat) used for sanity checks.
INDIA_BBOX = (68.0, 6.0, 98.0, 37.5)

# Charging speed classes, by charger rating in kW.
SPEED_CLASSES = [
    ("Slow", "up to 3.3 kW"),
    ("AC", "7-14 kW"),
    ("DC", "15-24 kW"),
    ("Fast DC", "25-120 kW"),
]


def speed_class(kw: float) -> int:
    if kw <= 3.4:
        return 0
    if kw < 15:
        return 1
    if kw < 25:
        return 2
    return 3


def haversine_km(lat1, lon1, lat2, lon2) -> float:
    r = math.radians
    dlat, dlon = r(lat2 - lat1), r(lon2 - lon1)
    a = math.sin(dlat / 2) ** 2 + math.cos(r(lat1)) * math.cos(r(lat2)) * math.sin(dlon / 2) ** 2
    return 2 * 6371 * math.asin(math.sqrt(a))
