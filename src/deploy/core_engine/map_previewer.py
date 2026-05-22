"""
Map preview generator [WO-001-v0.4 Task 2/3/4].

Generates a standalone Leaflet.js HTML file showing all vegetation index layers
(NDVI, EVI, NDRE, SAVI, GNDVI) via GEE getMapId() tile URLs.

No ee.batch.Export.image is used anywhere in this module.
Tile URLs expire in ~48 hours — this is an engineering preview tool only.

NDRE is skipped with a WARNING log when sensor is Landsat (L8/L9),
as Landsat has no Red Edge band.

Output: 04_Test/result_output/canopysense_visuals.html
"""

from __future__ import annotations

import json
import logging
import os
import pathlib
from datetime import date, timedelta

import ee

logger = logging.getLogger(__name__)

_PROJECT_ROOT = pathlib.Path(__file__).parent.parent.parent
_DEFAULT_OUTPUT = _PROJECT_ROOT / "tests" / "result_output" / "canopysense_visuals.html"

# Visualization parameters per index band
_VIZ_PARAMS: dict[str, dict] = {
    "ndvi":  {"min": -0.2, "max": 0.9, "palette": ["red", "yellow", "green"]},
    "evi":   {"min": -0.2, "max": 0.9, "palette": ["red", "yellow", "green"]},
    "ndre":  {"min": -0.2, "max": 0.9, "palette": ["purple", "white", "green"]},
    "savi":  {"min": -0.2, "max": 0.9, "palette": ["#8B4513", "yellow", "green"]},
    "gndvi": {"min": -0.2, "max": 0.9, "palette": ["red", "yellow", "darkgreen"]},
}

_INDEX_LABELS: dict[str, str] = {
    "ndvi":  "NDVI",
    "evi":   "EVI",
    "ndre":  "NDRE (S2 only)",
    "savi":  "SAVI",
    "gndvi": "GNDVI",
}


def generate_preview(
    image: ee.Image,
    sensor: str,
    aoi_ee: ee.Geometry,
    date_label: str,
    blocks_geojson: dict | None = None,
    output_path: str | pathlib.Path | None = None,
) -> str:
    """
    Generate a standalone Leaflet HTML map preview from a processed GEE image.

    Args:
        image:          Processed image with ndvi/evi/savi/gndvi (+ ndre for S2) bands.
        sensor:         "S2", "L8", or "L9" — determines NDRE availability.
        aoi_ee:         AOI geometry used to center the map on the estate area.
        date_label:     Human-readable date string shown in the HTML info panel.
        blocks_geojson: Optional GeoJSON FeatureCollection dict of block polygons.
                        Each feature must have properties: block_id, code, name,
                        plant_year, clone_type, has_data (bool).
                        If provided, blocks are rendered as a polygon overlay
                        with green (has_data) or grey (skipped) styling.
        output_path:    Override default output path (optional).

    Returns:
        Absolute path string to the generated HTML file.
    """
    out = pathlib.Path(output_path) if output_path else _DEFAULT_OUTPUT
    out.parent.mkdir(parents=True, exist_ok=True)

    # Determine which bands to render — NDRE only for Sentinel-2
    bands: list[str] = ["ndvi", "evi", "savi", "gndvi"]
    if sensor == "S2":
        bands.insert(2, "ndre")
    else:
        logger.warning(
            "NDRE not available for sensor %s (Landsat has no Red Edge band) — "
            "layer skipped from map preview.",
            sensor,
        )

    # Map center from AOI centroid
    centroid = aoi_ee.centroid(maxError=1).coordinates().getInfo()
    center_lon, center_lat = centroid[0], centroid[1]

    # Clip image to AOI before generating tiles — tiles render only within estate boundary
    clipped = image.clip(aoi_ee)

    # Fetch tile URL for each band via getMapId()
    tile_layers: list[dict[str, str]] = []
    for band in bands:
        logger.info("Fetching getMapId tile URL for band: %s ...", band)
        map_id_obj = clipped.select(band).getMapId(_VIZ_PARAMS[band])
        tile_url = map_id_obj["tile_fetcher"].url_format
        tile_layers.append({"name": _INDEX_LABELS[band], "url": tile_url})
        logger.info("  %s tile URL acquired.", band)

    html = _render_html(
        tile_layers=tile_layers,
        center_lat=center_lat,
        center_lon=center_lon,
        date_label=date_label,
        sensor=sensor,
        blocks_geojson=blocks_geojson,
    )

    out.write_text(html, encoding="utf-8")
    logger.info("HTML map preview written: %s", out.resolve())
    return str(out.resolve())


def _render_html(
    tile_layers: list[dict[str, str]],
    center_lat: float,
    center_lon: float,
    date_label: str,
    sensor: str,
    blocks_geojson: dict | None = None,
) -> str:
    """Render the complete Leaflet HTML string with all tile layers injected."""

    # Build JavaScript variable declarations for each overlay layer
    overlay_js_lines: list[str] = []
    overlay_dict_entries: list[str] = []

    for i, layer in enumerate(tile_layers):
        var_name = f"layer_{i}"
        overlay_js_lines.append(
            f'    var {var_name} = L.tileLayer("{layer["url"]}", {{'
            f'maxZoom: 18, opacity: 0.85, attribution: "Google Earth Engine"}});'
        )
        overlay_dict_entries.append(f'      "{layer["name"]}": {var_name}')

    overlays_js_block  = "\n".join(overlay_js_lines)
    overlays_dict_block = ",\n".join(overlay_dict_entries)
    first_layer = "layer_0" if tile_layers else "osm"

    # Block overlay — embed GeoJSON inline as a JS variable
    blocks_js_block = ""
    blocks_layer_control_entry = ""
    if blocks_geojson:
        geojson_str = json.dumps(blocks_geojson, separators=(",", ":"))
        blocks_js_block = f"""
    // Plantation block boundaries overlay
    var blocksData = {geojson_str};

    function blockStyle(feature) {{
      return feature.properties.has_data
        ? {{color: "#2e7d32", weight: 2, fillColor: "#66bb6a", fillOpacity: 0.20}}
        : {{color: "#757575", weight: 1, fillColor: "#bdbdbd", fillOpacity: 0.10}};
    }}

    function onEachBlock(feature, layer) {{
      var p = feature.properties;
      var status = p.has_data
        ? '<span style="color:#2e7d32;font-weight:bold">&#10003; Data available</span>'
        : '<span style="color:#757575">&#10007; Skipped (cloud cover)</span>';
      layer.bindPopup(
        '<b>' + p.name + '</b> (' + p.code + ')<br/>' +
        'Block ID: ' + p.block_id + '<br/>' +
        'Plant Year: ' + (p.plant_year || '—') + '<br/>' +
        'Clone: ' + p.clone_type + '<br/>' +
        'Status: ' + status
      );
      layer.on('mouseover', function() {{ layer.setStyle({{weight: 3, fillOpacity: 0.35}}); }});
      layer.on('mouseout',  function() {{ blocksLayer.resetStyle(layer); }});
    }}

    var blocksLayer = L.geoJSON(blocksData, {{
      style: blockStyle,
      onEachFeature: onEachBlock
    }});
"""
        blocks_layer_control_entry = ',\n      "Block Boundaries": blocksLayer'

    # Legend for block layer
    legend_js = ""
    if blocks_geojson:
        legend_js = """
    // Block layer legend
    var legend = L.control({position: "bottomleft"});
    legend.onAdd = function() {
      var div = L.DomUtil.create("div");
      div.style.cssText = "background:rgba(255,255,255,0.92);padding:8px 12px;border-radius:5px;font-size:12px;box-shadow:0 1px 5px rgba(0,0,0,0.3)";
      div.innerHTML =
        '<b>Block Status</b><br/>' +
        '<span style="display:inline-block;width:12px;height:12px;background:#66bb6a;border:2px solid #2e7d32;margin-right:5px;vertical-align:middle"></span>Data available<br/>' +
        '<span style="display:inline-block;width:12px;height:12px;background:#bdbdbd;border:1px solid #757575;margin-right:5px;vertical-align:middle"></span>Skipped (cloud cover)';
      return div;
    };
    legend.addTo(map);
"""

    # Decide initial layers — add blocksLayer if present
    initial_layers = f"cartoLight, {first_layer}" + (", blocksLayer" if blocks_geojson else "")

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>CanopySense — Vegetation Index Map Preview</title>
  <link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css" />
  <script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
  <style>
    body  {{ margin: 0; padding: 0; font-family: Arial, sans-serif; }}
    #map  {{ height: 100vh; width: 100%; }}
    #info {{
      position: absolute; top: 10px; left: 50px; z-index: 1000;
      background: rgba(255, 255, 255, 0.93); padding: 10px 15px;
      border-radius: 6px; box-shadow: 0 2px 8px rgba(0,0,0,0.3);
      font-size: 13px; max-width: 320px;
    }}
    #info h3 {{ margin: 0 0 5px 0; font-size: 15px; color: #1a6b2e; }}
    #info .meta {{ color: #444; line-height: 1.6; }}
    #info .note {{ margin-top: 6px; font-size: 11px; color: #888; }}
  </style>
</head>
<body>
  <div id="info">
    <h3>CanopySense &mdash; Vegetation Indices</h3>
    <div class="meta">
      <div>Scene: <strong>{date_label}</strong></div>
      <div>Sensor: <strong>{sensor}</strong></div>
    </div>
    <div class="note">
      Toggle layers top-right. Click blocks for details.<br/>
      Tiles expire ~48h after generation (GEE getMapId).
    </div>
  </div>
  <div id="map"></div>
  <script>
    // CartoDB Positron — works without Referer header (safe for local file:// use)
    var cartoLight = L.tileLayer(
      "https://{{s}}.basemaps.cartocdn.com/light_all/{{z}}/{{x}}/{{y}}{{r}}.png", {{
      maxZoom: 19,
      subdomains: "abcd",
      attribution: "&copy; OpenStreetMap contributors &copy; CARTO"
    }});

    // CartoDB Dark — useful for vegetation index contrast
    var cartoDark = L.tileLayer(
      "https://{{s}}.basemaps.cartocdn.com/dark_all/{{z}}/{{x}}/{{y}}{{r}}.png", {{
      maxZoom: 19,
      subdomains: "abcd",
      attribution: "&copy; OpenStreetMap contributors &copy; CARTO"
    }});

{overlays_js_block}
{blocks_js_block}
    var map = L.map("map", {{
      center: [{center_lat:.6f}, {center_lon:.6f}],
      zoom: 13,
      layers: [{initial_layers}]
    }});

    var baseLayers = {{
      "Light (CartoDB)": cartoLight,
      "Dark (CartoDB)":  cartoDark
    }};
    var overlays = {{
{overlays_dict_block}{blocks_layer_control_entry}
    }};

    L.control.layers(baseLayers, overlays, {{collapsed: false}}).addTo(map);
{legend_js}
  </script>
</body>
</html>"""


# ---------------------------------------------------------------------------
# Standalone entry point
# ---------------------------------------------------------------------------

def main() -> None:
    """
    Standalone execution — runs the full pipeline and generates the HTML preview.
    Reads all blocks from the PostGIS DB to build the AOI.
    GEE credentials and DB connection read from 04_Test/.env.
    """
    from .ee_init import initialize_ee
    from .scene_selector import select_best_scene
    from .cloud_masking import apply_cloud_mask
    from .harmonization import prepare_image
    from .index_calculator import calculate_indices

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
        datefmt="%H:%M:%S",
    )

    # Load .env
    env_file = _PROJECT_ROOT / "tests" / ".env"
    if env_file.exists():
        try:
            from dotenv import load_dotenv
            load_dotenv(env_file)
        except ImportError:
            pass

    import psycopg2
    from shapely.geometry import mapping, shape

    initialize_ee()

    date_end = date.today().isoformat()
    date_start = (date.today() - timedelta(days=7)).isoformat()

    # Load AOI from DB blocks
    conn = psycopg2.connect(
        host=os.environ.get("PGHOST", "localhost"),
        port=int(os.environ.get("PGPORT", 5432)),
        dbname=os.environ.get("PGDATABASE", "canopysense"),
        user=os.environ.get("PGUSER", "postgres"),
        password=os.environ.get("PGPASSWORD", ""),
    )
    with conn.cursor() as cur:
        cur.execute(
            "SELECT ST_AsGeoJSON(ST_Union(geometry)) FROM canopysense.blocks;"
        )
        geojson_str = cur.fetchone()[0]
    conn.close()

    if not geojson_str:
        logger.error("No blocks found in DB. Cannot build AOI.")
        return

    aoi_ee = ee.Geometry(json.loads(geojson_str))

    scene = select_best_scene(aoi_ee, date_start, date_end)
    if scene.skip:
        logger.warning("No valid scene found for %s – %s.", date_start, date_end)
        return

    image = apply_cloud_mask(scene.image, scene.sensor)
    image = prepare_image(image, scene.sensor)
    image = calculate_indices(image, scene.sensor)

    date_label = f"{date_start} → {date_end}"
    generate_preview(image, scene.sensor, aoi_ee, date_label)


if __name__ == "__main__":
    main()
