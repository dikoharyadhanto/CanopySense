"""
Deterministic scene selection [FR-01].

Priority tiers for a 7-day window:
  Tier 1: Sentinel-2,  valid_pixel_ratio >= 0.6  → selected, low_quality=False
  Tier 2: Sentinel-2,  valid_pixel_ratio >= 0.2  → selected, low_quality=False
  Tier 3: Landsat 8/9, valid_pixel_ratio >= 0.2  → selected, low_quality=(ratio < 0.6)
  Skip:   All sensors  valid_pixel_ratio <  0.2  → skip ingestion, "No Reliable Data"

valid_pixel_ratio computation:
  - S2:      Cloud Score+ (cs_cdf > 0.60) mask applied over AOI geometry.
  - Landsat: QA_PIXEL bitwise mask (cloud bit 3 + shadow bit 4) over AOI geometry.
  - Ratio = fraction of valid pixels (mean of binary mask) over the estate AOI.

[FR-07]: Landsat scenes selected in tier 3 with 0.2 <= valid_pixel_ratio < 0.6
         are flagged low_quality=True. This is a data quality metadata flag,
         NOT a rejection gate.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

import ee

logger = logging.getLogger(__name__)

# GEE collection IDs
_S2_COLLECTION   = "COPERNICUS/S2_SR_HARMONIZED"
_CS_PLUS_COL     = "GOOGLE/CLOUD_SCORE_PLUS/V1/S2_HARMONIZED"
_L8_COLLECTION   = "LANDSAT/LC08/C02/T1_L2"
_L9_COLLECTION   = "LANDSAT/LC09/C02/T1_L2"

# Cloud Score+ clear-sky threshold: cs_cdf > this = CLEAR (keep)
# cs_cdf is the probability a pixel is CLEAR — higher = clearer.
_CS_THRESHOLD = 0.60

# valid_pixel_ratio thresholds
_RATIO_HIGH = 0.6   # Tier 1 / low_quality boundary
_RATIO_MIN  = 0.2   # Minimum acceptable ratio

# QA_PIXEL cloud/shadow bit positions (Landsat C2)
_QA_CLOUD_BIT  = 1 << 3   # bit 3: cloud
_QA_SHADOW_BIT = 1 << 4   # bit 4: cloud shadow


@dataclass
class SceneResult:
    """Result of deterministic scene selection for a given time window."""
    image: ee.Image | None
    sensor: str            # "S2", "L8", "L9", or "SKIP"
    valid_pixel_ratio: float
    low_quality: bool      # True if Landsat 0.2 <= ratio < 0.6 [FR-07]
    skip: bool             # True = no valid data found, do not ingest
    reason: str            # Human-readable selection outcome


def select_best_scene(
    aoi_ee: ee.Geometry,
    date_start: str,
    date_end: str,
) -> SceneResult:
    """
    Select the best available satellite scene for a given 7-day window.

    Args:
        aoi_ee:     Earth Engine geometry representing the union of target estates.
        date_start: ISO date string, inclusive, e.g. "2025-01-01".
        date_end:   ISO date string, exclusive, e.g. "2025-01-08".

    Returns:
        SceneResult with the selected image, sensor, valid_pixel_ratio, and flags.
    """
    # --- Tier 1 & 2: Sentinel-2 ---
    s2_result = _best_s2_scene(aoi_ee, date_start, date_end)
    if s2_result is not None:
        image, ratio = s2_result
        tier = "1" if ratio >= _RATIO_HIGH else "2"
        logger.info(
            "Scene selected: S2 (tier %s), valid_pixel_ratio=%.3f", tier, ratio
        )
        return SceneResult(
            image=image,
            sensor="S2",
            valid_pixel_ratio=ratio,
            low_quality=False,
            skip=False,
            reason=f"S2 selected (tier {tier})",
        )

    # --- Tier 3: Landsat 8 / 9 ---
    ls_result = _best_landsat_scene(aoi_ee, date_start, date_end)
    if ls_result is not None:
        image, ratio, sensor_id = ls_result
        # FR-07: flag Landsat scenes where ratio is in [0.2, 0.6)
        low_quality = ratio < _RATIO_HIGH
        logger.info(
            "Scene selected: %s (tier 3), valid_pixel_ratio=%.3f, low_quality=%s",
            sensor_id, ratio, low_quality,
        )
        return SceneResult(
            image=image,
            sensor=sensor_id,
            valid_pixel_ratio=ratio,
            low_quality=low_quality,
            skip=False,
            reason=f"{sensor_id} selected (tier 3), low_quality={low_quality}",
        )

    # --- Skip: no valid data ---
    logger.warning(
        "No valid scene found for window %s – %s. Skipping ingestion.",
        date_start, date_end,
    )
    return SceneResult(
        image=None,
        sensor="SKIP",
        valid_pixel_ratio=0.0,
        low_quality=False,
        skip=True,
        reason="No Reliable Data",
    )


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _compute_s2_valid_ratio(
    cs_img: ee.Image, aoi: ee.Geometry
) -> ee.Number:
    """
    Compute valid pixel ratio for an S2 image using Cloud Score+.

    cs_cdf polarity: HIGHER value = MORE likely clear.
      - KEEP (unmask) pixels where cs_cdf > 0.60
      - MASK (discard) pixels where cs_cdf <= 0.60

    Ratio = mean of binary clear mask over all AOI pixels (including masked).
    """
    # Binary mask: 1 = clear, 0 = cloudy
    clear_mask = cs_img.select("cs_cdf").gt(_CS_THRESHOLD)
    # unmask(0) ensures masked pixels count as 0 in the denominator
    ratio = (
        clear_mask.unmask(0)
        .rename("valid")
        .reduceRegion(
            reducer=ee.Reducer.mean(),
            geometry=aoi,
            scale=10,
            maxPixels=int(1e9),
        )
        .getNumber("valid")
    )
    return ratio


def _best_s2_scene(
    aoi: ee.Geometry, date_start: str, date_end: str
) -> tuple[ee.Image, float] | None:
    """
    Find the S2 scene with the highest valid_pixel_ratio in the time window.
    Returns (image, ratio) if ratio >= _RATIO_MIN, else None.
    """
    s2_col = (
        ee.ImageCollection(_S2_COLLECTION)
        .filterDate(date_start, date_end)
        .filterBounds(aoi)
    )
    cs_col = (
        ee.ImageCollection(_CS_PLUS_COL)
        .filterDate(date_start, date_end)
        .filterBounds(aoi)
    )

    # Join Cloud Score+ images to S2 images by system:index (same tile/granule ID)
    joined = ee.Join.saveFirst("cs_img").apply(
        primary=s2_col,
        secondary=cs_col,
        condition=ee.Filter.equals(
            leftField="system:index", rightField="system:index"
        ),
    )

    if joined.size().getInfo() == 0:
        logger.debug("No S2 scenes found for window %s – %s.", date_start, date_end)
        return None

    def _add_ratio(img: ee.Image) -> ee.Image:
        cs_img = ee.Image(img.get("cs_img"))
        ratio = _compute_s2_valid_ratio(cs_img, aoi)
        return img.set("valid_pixel_ratio", ratio)

    col_with_ratio = ee.ImageCollection(joined).map(_add_ratio)

    # Select scene with highest ratio (deterministic: sort descending, take first)
    best = col_with_ratio.sort("valid_pixel_ratio", ascending=False).first()
    ratio_val: float | None = best.get("valid_pixel_ratio").getInfo()

    if ratio_val is None or ratio_val < _RATIO_MIN:
        logger.debug(
            "Best S2 ratio=%.3f below minimum threshold %.1f.",
            ratio_val or 0.0, _RATIO_MIN,
        )
        return None

    return best, ratio_val


def _compute_landsat_valid_ratio(
    image: ee.Image, aoi: ee.Geometry
) -> ee.Number:
    """
    Compute valid pixel ratio for a Landsat image using QA_PIXEL bitwise masking.
    Masks cloud (bit 3) and cloud shadow (bit 4).
    """
    qa = image.select("QA_PIXEL")
    clear_mask = (
        qa.bitwiseAnd(_QA_CLOUD_BIT).eq(0)
        .And(qa.bitwiseAnd(_QA_SHADOW_BIT).eq(0))
    )
    ratio = (
        clear_mask.unmask(0)
        .rename("valid")
        .reduceRegion(
            reducer=ee.Reducer.mean(),
            geometry=aoi,
            scale=30,
            maxPixels=int(1e9),
        )
        .getNumber("valid")
    )
    return ratio


def _best_landsat_scene(
    aoi: ee.Geometry, date_start: str, date_end: str
) -> tuple[ee.Image, float, str] | None:
    """
    Find the best Landsat 8 or 9 scene with the highest valid_pixel_ratio.
    Returns (image, ratio, sensor_id) if ratio >= _RATIO_MIN, else None.
    """
    l8_tagged = (
        ee.ImageCollection(_L8_COLLECTION)
        .filterDate(date_start, date_end)
        .filterBounds(aoi)
        .map(lambda img: img.set("sensor_id", "L8"))
    )
    l9_tagged = (
        ee.ImageCollection(_L9_COLLECTION)
        .filterDate(date_start, date_end)
        .filterBounds(aoi)
        .map(lambda img: img.set("sensor_id", "L9"))
    )

    merged = l8_tagged.merge(l9_tagged)

    if merged.size().getInfo() == 0:
        logger.debug("No Landsat scenes found for window %s – %s.", date_start, date_end)
        return None

    def _add_ratio(img: ee.Image) -> ee.Image:
        ratio = _compute_landsat_valid_ratio(img, aoi)
        return img.set("valid_pixel_ratio", ratio)

    col_with_ratio = merged.map(_add_ratio)

    best = col_with_ratio.sort("valid_pixel_ratio", ascending=False).first()
    ratio_val: float | None = best.get("valid_pixel_ratio").getInfo()
    sensor_id: str | None  = best.get("sensor_id").getInfo()

    if ratio_val is None or ratio_val < _RATIO_MIN:
        logger.debug(
            "Best Landsat ratio=%.3f below minimum threshold %.1f.",
            ratio_val or 0.0, _RATIO_MIN,
        )
        return None

    return best, ratio_val, sensor_id
