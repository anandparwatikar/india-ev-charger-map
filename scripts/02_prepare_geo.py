"""Prepare the basemap and the routing network.

Outputs (committed):
  data/geo/india_states_simplified.geojson  state outlines, simplified for the web map
  data/geo/india_highways.geojson           Natural Earth roads that fall inside India
  data/geo/highway_graph.json               routable graph: node coordinates + weighted edges
"""
import collections
import json

from shapely import prepared
from shapely.geometry import mapping, shape
from shapely.ops import unary_union

from common import DOWNLOADS, GEO, INDIA_BBOX, haversine_km


def rnd(obj, nd=3):
    if isinstance(obj, (list, tuple)):
        if obj and isinstance(obj[0], (int, float)):
            return [round(obj[0], nd), round(obj[1], nd)]
        return [rnd(x, nd) for x in obj]
    return obj


def states():
    src = json.load(open(DOWNLOADS / "states.geojson"))
    out, geoms = [], []
    for f in src["features"]:
        g = shape(f["geometry"]).buffer(0).simplify(0.01, preserve_topology=True)
        geoms.append(g)
        m = mapping(g)
        out.append({"type": "Feature", "properties": {"n": f["properties"]["ST_NM"]},
                    "geometry": {"type": m["type"], "coordinates": rnd(m["coordinates"])}})
    json.dump({"type": "FeatureCollection", "features": out},
              open(GEO / "india_states_simplified.geojson", "w"), separators=(",", ":"))
    print(f"states    {len(out)} features")
    return unary_union(geoms).simplify(0.02).buffer(0.05)


def roads(india):
    x0, y0, x1, y1 = INDIA_BBOX
    src = json.load(open(DOWNLOADS / "ne_10m_roads.geojson"))
    # Cheap bounding-box pass first (the worldwide file is large), then a polygon test.
    cand = []
    for f in src["features"]:
        g = f["geometry"]
        lines = g["coordinates"] if g["type"] == "MultiLineString" else [g["coordinates"]]
        if any(x0 <= x <= x1 and y0 <= y <= y1 for l in lines for x, y in l[:1] + l[-1:]):
            cand.append(f)
    del src
    p = prepared.prep(india)
    keep = [f for f in cand if p.intersects(shape(f["geometry"]))]
    for f in keep:
        f["properties"] = {k: f["properties"].get(k) for k in ("type", "name", "length_km")}
    json.dump({"type": "FeatureCollection", "features": keep},
              open(GEO / "india_highways.geojson", "w"), separators=(",", ":"))
    km = sum(f["properties"]["length_km"] or 0 for f in keep)
    print(f"roads     {len(keep)} features, about {km:,.0f} km")
    return keep


def graph(features):
    nodes, coords = {}, []

    def nid(lon, lat):
        k = (round(lat, 4), round(lon, 4))
        if k not in nodes:
            nodes[k] = len(coords)
            coords.append(k)
        return nodes[k]

    edges, ends, lines = {}, [], []
    for f in features:
        g = f["geometry"]
        for l in (g["coordinates"] if g["type"] == "MultiLineString" else [g["coordinates"]]):
            ids = [nid(x, y) for x, y in l]
            lines.append(ids)
            ends += [ids[0], ids[-1]]
            for a, b in zip(ids, ids[1:]):
                if a != b:
                    edges[(min(a, b), max(a, b))] = haversine_km(*coords[a], *coords[b])

    # Natural Earth lines do not always share end points. Join each dangling end
    # to the nearest vertex of a different line within 3 km.
    deg = collections.Counter()
    for a, b in edges:
        deg[a] += 1
        deg[b] += 1
    grid = collections.defaultdict(list)
    for i, (la, lo) in enumerate(coords):
        grid[(int(la * 20), int(lo * 20))].append(i)
    line_of = collections.defaultdict(set)
    for li, ids in enumerate(lines):
        for i in ids:
            line_of[i].add(li)
    snapped = 0
    for e in set(ends):
        if deg[e] > 1:
            continue
        la, lo = coords[e]
        best = None
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                for j in grid[(int(la * 20) + dx, int(lo * 20) + dy)]:
                    if j == e or line_of[j] & line_of[e]:
                        continue
                    d = haversine_km(*coords[e], *coords[j])
                    if d < 3 and (best is None or d < best[0]):
                        best = (d, j)
        if best:
            edges[(min(e, best[1]), max(e, best[1]))] = best[0]
            snapped += 1

    # Keep the largest connected component.
    adj = collections.defaultdict(list)
    for a, b in edges:
        adj[a].append(b)
        adj[b].append(a)
    comp, label = {}, 0
    for s in adj:
        if s in comp:
            continue
        stack = [s]
        comp[s] = label
        while stack:
            u = stack.pop()
            for v in adj[u]:
                if v not in comp:
                    comp[v] = label
                    stack.append(v)
        label += 1
    main = collections.Counter(comp.values()).most_common(1)[0][0]
    keep = [i for i in range(len(coords)) if comp.get(i) == main]
    remap = {o: n for n, o in enumerate(keep)}
    out_c = [[round(coords[i][0], 4), round(coords[i][1], 4)] for i in keep]
    out_e = [[remap[a], remap[b], round(d, 2)] for (a, b), d in edges.items() if a in remap and b in remap]
    json.dump({"coords": out_c, "edges": out_e}, open(GEO / "highway_graph.json", "w"), separators=(",", ":"))
    total = sum(e[2] for e in out_e)
    print(f"graph     {len(out_c):,} nodes, {len(out_e):,} edges, {total:,.0f} km, "
          f"{snapped} gaps joined, {label} components before pruning")


def main():
    GEO.mkdir(parents=True, exist_ok=True)
    india = states()
    graph(roads(india))


if __name__ == "__main__":
    main()
