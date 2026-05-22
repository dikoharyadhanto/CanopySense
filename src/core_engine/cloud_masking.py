"""
Cloud masking [FR-02].

Dual-layer masking strategy:

Primary — Cloud Score+ (S2 only):
  Dataset: GOOGLE/CLOUD_SCORE_PLUS/V1/S2_HARMONIZED
  cs_cdf polarity: HIGHER value = MORE likely CLEAR.
    KEEP (unmask) pixels where cs_cdf > 0.60  (≥60% probability of clear sky)
    MASK (discard) pixels where cs_cdf <= 0.60 (likely cloudy)

Secondary safety net (catches residual cloud/shadow after primary filter):
  S2:      SCL band exclusion — saturated (1), cloud shadow (3),
           medium cloud (8), high cloud (9), thin cirrus (10).
  Landsat: QA_PIXEL bitwise — cloud bit 3, cloud shadow bit 4.

Note: For Landsat, Cloud Score+ is not available. QA_PIXEL is the sole filter.
"""

from __future__ import annotations

import logging

import ee

logger = logging.getLogger(__name__)

_CS_PLUS_COL = "GOOGLE/CLOUD_SCORE_PLUS/V1/S2_HARMONIZED"

# Cloud Score+ threshold: cs_cdf > this = CLEAR (keep)
_CS_THRESHOLD = 0.60

# QA_PIXEL cloud/shadow bit positions (Landsat C2)
_QA_CLOUD_BIT  = 1 << 3   # bit 3: cloud
_QA_SHADOW_BIT = 1 << 4   # bit 4: cloud shadow


def apply_cloud_mask(image: ee.Image, sensor: str) -> ee.Image:
    """
    Apply dual-layer cloud masking to the input image.

    Args:
        image:  Raw satellite image (S2 or Landsat).
        sensor: "S2", "L8", or "L9".

    Returns:
        Image with cloud and shadow pixels masked out.

    Raises:
        ValueError: If sensor is not one of "S2", "L8", "L9".
    """
    if sensor == "S2":
        return _mask_s2(image)
    elif sensor in ("L8", "L9"):
        return _mask_landsat(image)
    else:
        raise ValueError(f"Unknown sensor: {sensor!r}. Expected 'S2', 'L8', or 'L9'.")


# ---------------------------------------------------------------------------
# Sensor-specific masking
# ---------------------------------------------------------------------------

def _mask_s2(image: ee.Image) -> ee.Image:
    """
    Sentinel-2 dual-layer masking:

    Layer 1 (Primary): Cloud Score+ — discard pixels where cs_cdf <= 0.60.
      cs_cdf represents the probability a pixel is CLEAR.
      We KEEP pixels where cs_cdf > 0.60 (clear sky confirmed).

    Layer 2 (Secondary): SCL band — excludes residual cloud/shadow pixels
      that Cloud Score+ may miss:
        SCL 1:  Saturated / Defective
        SCL 3:  Cloud Shadow
        SCL 8:  Cloud Medium Probability
        SCL 9:  Cloud High Probability
        SCL 10: Thin Cirrus
    """
    # --- Primary: Cloud Score+ ---
    # Fetch matching CS+ image by system:index (same tile granule ID)
    cs_img = (
        ee.ImageCollection(_CS_PLUS_COL)
        .filter(ee.Filter.equals("system:index", image.get("system:index")))
        .first()
    )
    # KEEP where cs_cdf > threshold (higher cs_cdf = clearer)
    cs_mask = cs_img.select("cs_cdf").gt(_CS_THRESHOLD)
    image = image.updateMask(cs_mask)

    # --- Secondary: SCL band ---
    scl = image.select("SCL")
    scl_bad = (
        scl.eq(1)     # Saturated / Defective
        .Or(scl.eq(3))   # Cloud Shadow
        .Or(scl.eq(8))   # Cloud Medium Probability
        .Or(scl.eq(9))   # Cloud High Probability
        .Or(scl.eq(10))  # Thin Cirrus
    )
    scl_mask = scl_bad.Not()   # Keep where NOT flagged as bad
    image = image.updateMask(scl_mask)

    return image


def _mask_landsat(image: ee.Image) -> ee.Image:
    """
    Landsat C2 masking using QA_PIXEL bitwise flags.
    Masks cloud (bit 3) and cloud shadow (bit 4).
    Cloud Score+ is not available for Landsat; QA_PIXEL is the sole filter.
    """
    qa = image.select("QA_PIXEL")
    # Keep pixels where both cloud and shadow bits are 0
    clear_mask = (
        qa.bitwiseAnd(_QA_CLOUD_BIT).eq(0)
        .And(qa.bitwiseAnd(_QA_SHADOW_BIT).eq(0))
    )
    return image.updateMask(clear_mask)
