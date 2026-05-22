"""
generate_test_blocks.py
========================
Subdivides the estate-level shapefile into a grid of dummy block polygons
for use in testing the CanopySense Core Engine.

Approach:
  - Load estate shapefile.
  - For each estate polygon, create a regular grid of smaller cells that
    intersect the estate boundary (clipped to actual estate shape).
  - Assign sequential integer block_id values starting from 1.
  - Output: tests/test_blocks.geojson

Usage:
    python tests/generate_test_blocks.py

Output:
    tests/test_blocks.geojson

Shapefile requirement:
    Place your estate shapefile at:
      tests/Dummy_rubber_estate_SHP/dummy_rubber_estate.shp
    Or edit the SHAPEFILE constant below to point to any compatible .shp file.
    The script exits with a clear error when the shapefile is absent.
"""

from __future__ import annotations

import json
import pathlib
import sys

import geopandas as gpd
import numpy as np
from shapely.geometry import box, mapping

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

SHAPEFILE = pathlib.Path(__file__).parent / "Dummy_rubber_estate_SHP" / "dummy_rubber_estate.shp"
OUTPUT    = pathlib.Path(__file__).parent / "test_blocks.geojson"

# Target block cell size in degrees (~0.01° ≈ 1.1 km at equator; typical rubber block ~50–200 ha)
CELL_SIZE_DEG = 0.008   # ~0.8 km side → ~64 ha cells, reasonable for rubber blocks

# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    if not SHAPEFILE.exists():
        print(
            f"ERROR: Shapefile not found: {SHAPEFILE}\n"
            f"\n"
            f"  To generate test blocks, place the estate shapefile at:\n"
            f"    {SHAPEFILE}\n"
            f"\n"
            f"  Or edit the SHAPEFILE constant at the top of this script to\n"
            f"  point to any compatible .shp file with estate polygon geometry.\n"
            f"\n"
            f"  No shapefile is committed to the repo (no real data). Obtain\n"
            f"  a dummy shapefile or run against a real estate boundary."
        )
        sys.exit(1)

    print(f"Loading estate shapefile: {SHAPEFILE}")
    gdf = gpd.read_file(SHAPEFILE)

    # Reproject to WGS84 if needed
    if gdf.crs and gdf.crs.to_epsg() != 4326:
        print(f"  Reprojecting from {gdf.crs} → EPSG:4326")
        gdf = gdf.to_crs(epsg=4326)

    print(f"  Estate count: {len(gdf)}")
    print(f"  Columns: {list(gdf.columns)}")
    print(f"  Bounds: {gdf.total_bounds}")

    blocks = []
    block_id = 1

    for _, estate in gdf.iterrows():
        geom = estate.geometry
        minx, miny, maxx, maxy = geom.bounds

        # Build grid of cells covering the estate bounding box
        xs = np.arange(minx, maxx, CELL_SIZE_DEG)
        ys = np.arange(miny, maxy, CELL_SIZE_DEG)

        for x in xs:
            for y in ys:
                cell = box(x, y, x + CELL_SIZE_DEG, y + CELL_SIZE_DEG)
                clipped = geom.intersection(cell)

                # Only keep cells with meaningful area (>5% of full cell)
                if clipped.is_empty or clipped.area < (CELL_SIZE_DEG ** 2) * 0.05:
                    continue

                blocks.append({
                    "type": "Feature",
                    "properties": {
                        "block_id": block_id,
                    },
                    "geometry": mapping(clipped),
                })
                block_id += 1

    if not blocks:
        print("ERROR: No block cells generated. Check estate geometry and CELL_SIZE_DEG.")
        return

    geojson = {
        "type": "FeatureCollection",
        "features": blocks,
    }

    OUTPUT.write_text(json.dumps(geojson, indent=2), encoding="utf-8")
    print(f"\nDone. Generated {len(blocks)} blocks → {OUTPUT}")
    print("Columns in output: block_id (integer)")
    print("Ready for use as input to core_engine.run_export().")


if __name__ == "__main__":
    main()
