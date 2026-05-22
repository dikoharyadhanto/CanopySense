"""
Hard quality gate [FR-03].

Validates valid_pixel_ratio >= 0.2 per estate geometry.

If an estate does not meet the threshold, it is excluded from the export.
No carry-forward of previous week's data is performed.
The downstream system receives "No Reliable Data" for skipped estates.

valid_pixel_ratio computation approach:
  A 'valid_mask' band (1=valid pixel, 0=masked pixel) is added to the image
  before export. Since this band is fully unmasked (values 0 or 1), applying
  ee.Reducer.mean() in reduceRegions yields the fraction of valid pixels per
  estate geometry — i.e., valid_pixel_ratio.

  Index bands (still masked) also use ee.Reducer.mean(), which computes the
  mean only over valid (unmasked) pixels — correct behavior.
"""

from __future__ import annotations

import ee

# Minimum valid pixel fraction required for ingestion
VALID_PIXEL_RATIO_THRESHOLD = 0.2


def build_valid_mask_band(image: ee.Image) -> ee.Image:
    """
    Add a 'valid_mask' band to the image representing pixel validity.

    The 'valid_mask' band is fully unmasked (0 for invalid, 1 for valid),
    so that ee.Reducer.mean() over it yields valid_pixel_ratio per estate.
    All index bands retain their existing mask (cloud-masked pixels excluded
    from index means).

    Args:
        image: Image after cloud masking, harmonization, and index calculation.

    Returns:
        Image with an added 'valid_mask' band.
    """
    # mask() returns a 0/1 image matching the first band's mask.
    # unmask(0) ensures masked pixels have value 0 (no data) so they count
    # toward the total pixel denominator when computing the mean.
    valid_mask = (
        image.select([0])
        .mask()
        .rename("valid_mask")
        .unmask(0)
    )
    return image.addBands(valid_mask)


def passes_quality_gate(valid_pixel_ratio: float) -> bool:
    """
    Return True if valid_pixel_ratio meets the minimum ingestion threshold.

    Args:
        valid_pixel_ratio: Fraction of valid pixels in [0.0, 1.0].

    Returns:
        True if >= 0.2 (VALID_PIXEL_RATIO_THRESHOLD), False otherwise.
    """
    return valid_pixel_ratio >= VALID_PIXEL_RATIO_THRESHOLD
