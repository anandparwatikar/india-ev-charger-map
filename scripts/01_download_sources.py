"""Download the third-party geographic sources into data/geo/_downloads/.

- DataMeet India state boundaries (GeoJSON)
- Natural Earth 1:10m roads (GeoJSON, worldwide)
- Natural Earth 1:10m populated places (GeoJSON, worldwide)

These files are large (about 70 MB together) and are not committed to the repo.
"""
import urllib.request
from common import DOWNLOADS

SOURCES = {
    "states.geojson": "https://raw.githubusercontent.com/datameet/maps/master/website/docs/data/geojson/states.geojson",
    "ne_10m_roads.geojson": "https://raw.githubusercontent.com/nvkelso/natural-earth-vector/master/geojson/ne_10m_roads.geojson",
    "ne_10m_populated_places_simple.geojson": "https://raw.githubusercontent.com/nvkelso/natural-earth-vector/master/geojson/ne_10m_populated_places_simple.geojson",
}


def main():
    DOWNLOADS.mkdir(parents=True, exist_ok=True)
    for name, url in SOURCES.items():
        target = DOWNLOADS / name
        if target.exists():
            print(f"skip   {name} (already downloaded)")
            continue
        print(f"fetch  {name}")
        urllib.request.urlretrieve(url, target)
        print(f"       {target.stat().st_size / 1e6:.1f} MB")


if __name__ == "__main__":
    main()
