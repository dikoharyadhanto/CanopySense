"""
generate_test_blocks.py
========================
Exports the canonical Phase 1 block polygons from BT_BLOK_SEMBAWA shapefile
as a GeoJSON file for use in testing the CanopySense Core Engine.

Normalization rules applied (per FMN-PLAN Section 10 Obs 2):
  - block_id  : OBJECTID (sequential integer, 1-indexed, no nulls in source)
  - geometry  : original Polygon/MultiPolygon reprojected EPSG:32748 → EPSG:4326
  - Invalid geometries are repaired via buffer(0) before export
  - Output CRS is EPSG:4326 (GeoJSON default; no crs member written per RFC 7946)

These are the ACTUAL block boundaries — not synthetic grid cells. Using real
block shapes ensures GEE scene selection and export targets the same spatial
extent as the production DB and frontend map.

Usage:
    python tests/generate_test_blocks.py

Output:
    tests/test_blocks.geojson
"""

from __future__ import annotations

import json
import pathlib
import sys

import geopandas as gpd
from shapely.geometry import mapping

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

SHAPEFILE = pathlib.Path(__file__).parent.parent / "references" / "SHP_data" / "BT_BLOK_SEMBAWA" / "BT_BLOK_SEMBAWA.shp"
OUTPUT    = pathlib.Path(__file__).parent / "test_blocks.geojson"

# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    if not SHAPEFILE.exists():
        print(
            f"ERROR: Canonical shapefile not found: {SHAPEFILE}\n"
            f"\n"
            f"  BT_BLOK_SEMBAWA is the official Phase 1 polygon fixture.\n"
            f"  Ensure references/SHP_data/BT_BLOK_SEMBAWA/ is present."
        )
        sys.exit(1)

    print(f"Loading canonical shapefile: {SHAPEFILE}")
    gdf = gpd.read_file(SHAPEFILE)
    print(f"  Source CRS  : {gdf.crs}")
    print(f"  Block count : {len(gdf)}")
    print(f"  Columns     : {list(gdf.columns)}")
    print(f"  Bounds      : {gdf.total_bounds}")

    # Reproject to EPSG:4326 (GeoJSON default)
    if gdf.crs and gdf.crs.to_epsg() != 4326:
        print(f"  Reprojecting {gdf.crs} → EPSG:4326")
        gdf = gdf.to_crs(epsg=4326)

    # Repair any invalid geometries
    invalid_mask = ~gdf.geometry.is_valid
    n_invalid = invalid_mask.sum()
    if n_invalid > 0:
        print(f"  Repairing {n_invalid} invalid geometry/ies via buffer(0)")
        gdf.loc[invalid_mask, "geometry"] = gdf.loc[invalid_mask, "geometry"].buffer(0)

    # Build GeoJSON features — keep only block_id to match core_engine interface
    features = []
    for _, row in gdf.iterrows():
        features.append({
            "type": "Feature",
            "properties": {
                "block_id": int(row["OBJECTID"]),  # normalization rule: OBJECTID → block_id
            },
            "geometry": mapping(row.geometry),
        })

    if not features:
        print("ERROR: No features generated.")
        sys.exit(1)

    geojson = {
        "type": "FeatureCollection",
        "features": features,
    }

    OUTPUT.write_text(json.dumps(geojson, indent=2), encoding="utf-8")
    print(f"\nDone. {len(features)} blocks → {OUTPUT}")
    print("Normalization rules applied:")
    print("  block_id  = OBJECTID (sequential integer, no synthetic grid subdivision)")
    print("  geometry  = actual block polygon/multipolygon, EPSG:32748 → EPSG:4326")
    print("  repairs   = buffer(0) on any invalid geometry before export")


if __name__ == "__main__":
    main()
