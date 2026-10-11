"""Clean the station list exported from the EV PCS PDF.

Problems in the source file and what this script does about them:
1. About 4,000 rows are shifted by one column (PDF-to-Excel artefact): the PIN code
   sits in Latitude, the latitude in Longitude, and the longitude is glued to the
   front of the connector type. The script finds the first valid (lat, lon) pair
   among the numeric fields and recovers the clean connector type.
2. 271 rows have an empty State (including all 223 Uttarakhand stations). The
   state is filled in from the station's coordinates.
3. Points that fall outside India, and rows with no usable pair, are written to
   a separate "unlocated" file instead of being dropped silently.

Outputs:
  data/processed/ev_stations_clean.csv
  data/processed/ev_stations_unlocated.csv
  data/processed/cleaning_report.json
"""
import json
import re

import numpy as np
import pandas as pd
from shapely.geometry import Point, shape
from shapely.strtree import STRtree

from common import GEO, PROCESSED, SOURCE_XLSX, SPEED_CLASSES, speed_class

TYPES = ["Combo (CCS-II+CHAdeMO)", "LEV DC Charge Point (IS-17017-2-7)", "DC Charge Point (IS-17017-2-7)",
         "DC Charge Point (IS-17017-2-6)", "LEV AC Charge point", "LEV DC", "Bharat AC-001", "Bharat DC-001",
         "Bharat AC", "Type-II AC", "Type II", "CCS-II", "CCS", "CHAdeMO", "CHADEMO"]
TYPES_BY_LEN = sorted(TYPES, key=len, reverse=True)
NUM = re.compile(r"-?\d+\.\d+|-?\d+")

# DataMeet state names -> names used in the station list
STATE_NAMES = {"Andaman & Nicobar Island": "Andaman & Nicobar", "Arunanchal Pradesh": "Arunachal Pradesh",
               "NCT of Delhi": "Delhi", "Dadara & Nagar Havelli": "Dadra & Nagar Haveli and Daman & Diu",
               "Daman & Diu": "Dadra & Nagar Haveli and Daman & Diu"}
OPERATOR_NAMES = {"Mahindra Automotive Manufacturers": "Mahindra", "Zeon charging": "Zeon Charging"}


def split_type(raw):
    s = str(raw).rstrip()
    for t in TYPES_BY_LEN:
        if s.lower().endswith(t.lower()):
            return ("CHAdeMO" if t == "CHADEMO" else t), s[: len(s) - len(t)]
    return s.strip(), ""


def in_box(lat, lon):
    return 6 <= lat <= 38 and 68 <= lon <= 98


def recover(lat, lon, prefix):
    if in_box(lat, lon):
        return lat, lon, "original"
    cands = [lat, lon] + [float(x) for x in NUM.findall(prefix)]
    for i in range(len(cands) - 1):
        a, b = cands[i], cands[i + 1]
        if in_box(a, b) and a != round(a):
            return a, b, "repaired"
    for i in range(len(cands) - 1):
        b, a = cands[i], cands[i + 1]
        if in_box(a, b):
            return a, b, "repaired"
    return np.nan, np.nan, "missing"


def main():
    df = pd.read_excel(SOURCE_XLSX, sheet_name="EV PCS Data")
    T = "Types of Chargers Installed/Connector"
    rows = []
    for r in df.to_dict("records"):
        ctype, prefix = split_type(r[T])
        lat, lon, status = recover(r["Latitude"], r["Longitude"], prefix)
        rows.append({"operator": OPERATOR_NAMES.get(r["CPO Name"], r["CPO Name"]),
                     "ownership": "Government" if str(r["Govt/Private"]).startswith("Govt") else "Private",
                     "state": r["State"] if isinstance(r["State"], str) else None,
                     "district": r["District"], "city": r["City/Village"],
                     "address": re.sub(r"\s+", " ", str(r["Location"])).strip(" -,"),
                     "latitude": lat, "longitude": lon, "connector_type": ctype,
                     "charger_kw": r["Charger Rating"], "connector_kw": r["Connector Rating"],
                     "connectors": int(r["No. of Connector"]), "coord_status": status})
    out = pd.DataFrame(rows)

    feats = json.load(open(GEO / "india_states_simplified.geojson"))["features"]
    geoms = [shape(f["geometry"]) for f in feats]
    names = [STATE_NAMES.get(f["properties"]["n"], f["properties"]["n"]) for f in feats]
    tree = STRtree(geoms)

    def state_at(lat, lon):
        p = Point(lon, lat)
        for i in tree.query(p):
            if geoms[i].contains(p):
                return names[i]
        i = tree.nearest(p)
        return names[i] if geoms[i].distance(p) < 0.1 else None   # ~10 km coastal tolerance

    geo_state = [state_at(a, b) if not np.isnan(a) else None for a, b in zip(out.latitude, out.longitude)]
    outside = out.latitude.notna() & pd.Series([g is None for g in geo_state])
    out.loc[outside, ["latitude", "longitude"]] = np.nan
    out.loc[outside, "coord_status"] = "outside_india"
    out["state_source"] = np.where(out.state.isna(), "from_coordinates", "source")
    blank = out.state.isna()
    out.loc[blank, "state"] = pd.Series(geo_state)[blank]
    out["speed_class"] = [SPEED_CLASSES[speed_class(k)][0] for k in out.charger_kw]

    PROCESSED.mkdir(parents=True, exist_ok=True)
    located = out[out.latitude.notna()]
    located.to_csv(PROCESSED / "ev_stations_clean.csv", index=False)
    out[out.latitude.isna()].to_csv(PROCESSED / "ev_stations_unlocated.csv", index=False)
    report = {"source_rows": len(out), "located": len(located),
              "coords_original": int((out.coord_status == "original").sum()),
              "coords_repaired": int((out.coord_status == "repaired").sum()),
              "coords_missing": int((out.coord_status == "missing").sum()),
              "outside_india": int(outside.sum()),
              "state_filled_from_coordinates": int(blank.sum()),
              "states_filled": out[out.state_source == "from_coordinates"].state.value_counts().to_dict()}
    json.dump(report, open(PROCESSED / "cleaning_report.json", "w"), indent=2)
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
