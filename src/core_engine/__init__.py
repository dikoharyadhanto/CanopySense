"""
core_engine — CanopySense GEE Core Engine (Tahap I).

Public API surface for the core satellite data extraction pipeline.

Typical usage:

    from core_engine import (
        initialize_ee,
        select_best_scene,
        apply_cloud_mask,
        prepare_image,
        calculate_indices,
        run_export,
    )

    initialize_ee()

    result = select_best_scene(aoi_ee, date_start, date_end)
    if result.skip:
        # No Reliable Data — do not ingest, no carry-forward
        return

    image = apply_cloud_mask(result.image, result.sensor)
    image = prepare_image(image, result.sensor)       # scale + rename + Roy harmonization
    image = calculate_indices(image, result.sensor)   # NDVI, EVI, SAVI, GNDVI, NDRE

    chunk_results = run_export(
        image=image,
        estates_gdf=estates_gdf,        # must contain 'block_id' column (int FK)
        export_folder="CanopySense_Exports",
        acquisition_date=date_start,    # exported as 'acquisition_date' column [FR-08]
        sensor=result.sensor,
        scene_low_quality=result.low_quality,
    )
"""

from .ee_init import initialize_ee
from .scene_selector import SceneResult, select_best_scene
from .cloud_masking import apply_cloud_mask
from .harmonization import prepare_image
from .index_calculator import calculate_indices
from .quality_gate import build_valid_mask_band, passes_quality_gate, VALID_PIXEL_RATIO_THRESHOLD
try:
    # async_engine requires geopandas — not installed in raster-serving environments
    from .async_engine import ChunkResult, run_export, DEFAULT_CHUNK_SIZE
except ImportError:
    pass
from .map_previewer import generate_preview

__all__ = [
    # Initialization
    "initialize_ee",
    # Scene selection
    "SceneResult",
    "select_best_scene",
    # Processing pipeline
    "apply_cloud_mask",
    "prepare_image",
    "calculate_indices",
    # Quality gate
    "build_valid_mask_band",
    "passes_quality_gate",
    "VALID_PIXEL_RATIO_THRESHOLD",
    # Export engine (GCS path — async_engine.py)
    "ChunkResult",
    "run_export",
    "DEFAULT_CHUNK_SIZE",
    # Map preview
    "generate_preview",
]
