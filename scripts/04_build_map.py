"""Bundle the cleaned data into the map and write index.html.

The map is one self-contained HTML file: station data, state outlines, the highway
graph and a place list for search are embedded as JSON. Only Leaflet and
Leaflet.markercluster (from cdnjs) and the web fonts are loaded from the internet.

Outputs:
  index.html             full HTML document (GitHub Pages, double-click to open)
  dist/artifact.html     page body only, for publishing as a Claude artifact
"""
import collections
import json

import pandas as pd

from common import DOWNLOADS, GEO, PROCESSED, ROOT, SRC, VENDOR, speed_class


def places(st):
    pl = {}
    src = DOWNLOADS / "ne_10m_populated_places_simple.geojson"
    if src.exists():
        for f in json.load(open(src))["features"]:
            q = f["properties"]
            if q.get("adm0name") == "India":
                pl[(q["name"].lower(), "")] = [q["name"], q.get("adm1name") or "", round(q["latitude"], 4),
                                                round(q["longitude"], 4), int(q.get("pop_max") or 0)]
    else:
        print("note: Natural Earth places not downloaded; search uses station towns only")
    nice = lambda s: str(s).title() if str(s).isupper() else str(s)
    for r in st.groupby(["city", "state"]).agg(lat=("latitude", "median"), lon=("longitude", "median"),
                                               c=("latitude", "size")).reset_index().itertuples():
        pl[(str(r.city).lower(), str(r.state).lower())] = [nice(r.city), str(r.state), round(r.lat, 4), round(r.lon, 4), -int(r.c)]
    for r in st.groupby(["district", "state"]).agg(lat=("latitude", "median"), lon=("longitude", "median"),
                                                   c=("latitude", "size")).reset_index().itertuples():
        if (str(r.district).lower(), str(r.state).lower()) not in pl:
            pl[("d:" + str(r.district).lower(), str(r.state).lower())] = [nice(r.district) + " district", str(r.state),
                                                                          round(r.lat, 4), round(r.lon, 4), -int(r.c)]
    return list(pl.values())


def road_chains(n_nodes, edges):
    """Merge runs of degree-2 nodes into polylines so the basemap draws fewer shapes."""
    adj = collections.defaultdict(list)
    for a, b, _ in edges:
        adj[a].append(b)
        adj[b].append(a)
    seen, chains = set(), []
    for u in adj:
        if len(adj[u]) == 2:
            continue
        for v in adj[u]:
            e = (min(u, v), max(u, v))
            if e in seen:
                continue
            ch, prev, cur = [u, v], u, v
            seen.add(e)
            while len(adj[cur]) == 2:
                nx = adj[cur][0] if adj[cur][0] != prev else adj[cur][1]
                e = (min(cur, nx), max(cur, nx))
                if e in seen:
                    break
                seen.add(e)
                ch.append(nx)
                prev, cur = cur, nx
            chains.append(ch)
    for a, b, _ in edges:
        if (min(a, b), max(a, b)) not in seen:
            chains.append([a, b])
    return chains


def main():
    st = pd.read_csv(PROCESSED / "ev_stations_clean.csv")
    report = json.load(open(PROCESSED / "cleaning_report.json"))
    st["sp"] = st.charger_kw.map(speed_class)
    ops = list(st.operator.value_counts().index)
    types = sorted(st.connector_type.unique())
    states = sorted(st.state.dropna().unique())
    dists = sorted(st.district.fillna("").astype(str).unique())
    cities = sorted(st.city.fillna("").astype(str).unique())
    di, ci = {d: i for i, d in enumerate(dists)}, {c: i for i, c in enumerate(cities)}
    num = lambda k: int(k) if float(k) == int(k) else float(k)
    cols = {"lat": [round(x, 5) for x in st.latitude], "lon": [round(x, 5) for x in st.longitude],
            "op": [ops.index(o) for o in st.operator], "sp": st.sp.tolist(), "kw": [num(k) for k in st.charger_kw],
            "n": st.connectors.astype(int).tolist(), "ty": [types.index(t) for t in st.connector_type],
            "st": [states.index(s) if isinstance(s, str) else -1 for s in st.state],
            "di": [di[d if isinstance(d, str) else ""] for d in st.district],
            "ci": [ci[c if isinstance(c, str) else ""] for c in st.city],
            "ad": st.address.fillna("").tolist(), "gv": [1 if o == "Government" else 0 for o in st.ownership]}
    g = json.load(open(GEO / "highway_graph.json"))
    pl = places(st)
    bundle = {"ops": ops, "types": types, "states": states, "dists": dists, "cities": cities, "s": cols,
              "places": pl, "g": {"c": g["coords"], "e": g["edges"], "ch": road_chains(len(g["coords"]), g["edges"])},
              "geo": json.load(open(GEO / "india_states_simplified.geojson")),
              "big": [[p[0], p[2], p[3]] for p in pl if p[4] >= 1_000_000],
              "meta": {"rows": report["source_rows"], "located": report["located"],
                       "repaired": report["coords_repaired"], "unlocated": report["source_rows"] - report["located"]}}
    data_js = "window.EVDATA=" + json.dumps(bundle, separators=(",", ":"), ensure_ascii=False).replace("</", "<\\/") + ";"

    body = (open(SRC / "template.html").read()
            .replace("/*__LEAFLET_CSS__*/", open(VENDOR / "leaflet-1.9.4.css").read())
            .replace("/*__CLUSTER_CSS__*/", open(VENDOR / "MarkerCluster-1.5.3.css").read())
            .replace("/*__DATA__*/", data_js))
    (ROOT / "dist").mkdir(exist_ok=True)
    (ROOT / "dist" / "artifact.html").write_text(body)
    head = ('<!doctype html><html lang="en"><head><meta charset="utf-8">'
            '<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">'
            '<style>:root{color-scheme:light}body{margin:0;font:14px system-ui}[hidden]{display:none!important}</style>'
            '</head><body>')
    (ROOT / "index.html").write_text(head + body + "</body></html>")
    print(f"index.html  {len(head + body) / 1e6:.2f} MB  ({len(st):,} stations, {len(pl):,} places)")


if __name__ == "__main__":
    main()
