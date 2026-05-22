"""
Spectral index calculation [FR-05].

Indices calculated from standardized [0,1] harmonized reflectance bands:

  NDVI  = (NIR - Red) / (NIR + Red)
  EVI   = 2.5 * (NIR - Red) / (NIR + 6*Red - 7.5*Blue + 1)   [Huete et al. 2002]
  SAVI  = ((NIR - Red) / (NIR + Red + 0.5)) * 1.5             [L=0.5, Huete 1988]
  GNDVI = (NIR - Green) / (NIR + Green)
  NDRE  = (RedEdge - Red) / (RedEdge + Red)                   [S2 only — B5 ~705nm]

[FR-07]: NDRE is computed for Sentinel-2 only (uses Red Edge Band B5 at ~705nm).
         Landsat has no Red Edge band; ndre is explicitly omitted for Landsat.
         The async_engine sets ndre=NULL in the export for Landsat records.

Note: No normalization is applied to index output (Spectral Preservation rule).
Note: Input image must have standardized band names from harmonization.prepare_image().
"""

from __future__ import annotations

import ee

# EVI coefficients — Huete et al. (2002)
_EVI_G  = 2.5   # gain factor
_EVI_C1 = 6.0   # aerosol resistance coefficient (red)
_EVI_C2 = 7.5   # aerosol resistance coefficient (blue)
_EVI_L  = 1.0   # canopy background adjustment

# SAVI soil adjustment factor — Huete (1988)
_SAVI_L = 0.5


def calculate_indices(image: ee.Image, sensor: str) -> ee.Image:
    """
    Append spectral index bands to the standardized reflectance image.

    Args:
        image:  Standardized [0,1] reflectance image (from harmonization.prepare_image).
                Expected bands: blue, green, red, nir, swir1, swir2
                               + red_edge for S2 only.
        sensor: "S2", "L8", or "L9".

    Returns:
        Input image with additional bands: ndvi, evi, savi, gndvi.
        For S2: also includes ndre band.
        For Landsat: ndre band is not added (set to NULL in export step).
    """
    image = _add_ndvi(image)
    image = _add_evi(image)
    image = _add_savi(image)
    image = _add_gndvi(image)

    if sensor == "S2":
        # NDRE uses S2 Red Edge Band B5 (~705 nm) — not available on Landsat
        image = _add_ndre(image)

    return image


# ---------------------------------------------------------------------------
# Index implementations
# ---------------------------------------------------------------------------

def _add_ndvi(image: ee.Image) -> ee.Image:
    """NDVI = (NIR - Red) / (NIR + Red)"""
    ndvi = image.normalizedDifference(["nir", "red"]).rename("ndvi")
    return image.addBands(ndvi)


def _add_evi(image: ee.Image) -> ee.Image:
    """
    EVI = G * (NIR - Red) / (NIR + C1*Red - C2*Blue + L)
    G=2.5, C1=6, C2=7.5, L=1  [Huete et al. 2002]
    """
    nir  = image.select("nir")
    red  = image.select("red")
    blue = image.select("blue")

    numerator   = nir.subtract(red).multiply(_EVI_G)
    denominator = (
        nir
        .add(red.multiply(_EVI_C1))
        .subtract(blue.multiply(_EVI_C2))
        .add(_EVI_L)
    )
    evi = numerator.divide(denominator).rename("evi")
    return image.addBands(evi)


def _add_savi(image: ee.Image) -> ee.Image:
    """
    SAVI = ((NIR - Red) / (NIR + Red + L)) * (1 + L),  L=0.5  [Huete 1988]
    """
    nir = image.select("nir")
    red = image.select("red")

    savi = (
        nir.subtract(red)
        .divide(nir.add(red).add(_SAVI_L))
        .multiply(1 + _SAVI_L)
        .rename("savi")
    )
    return image.addBands(savi)


def _add_gndvi(image: ee.Image) -> ee.Image:
    """GNDVI = (NIR - Green) / (NIR + Green)"""
    gndvi = image.normalizedDifference(["nir", "green"]).rename("gndvi")
    return image.addBands(gndvi)


def _add_ndre(image: ee.Image) -> ee.Image:
    """
    NDRE = (RedEdge - Red) / (RedEdge + Red)
    Uses Sentinel-2 Red Edge Band B5 at approximately 705 nm.
    Called for S2 sensor only — do not call for Landsat.
    """
    ndre = image.normalizedDifference(["red_edge", "red"]).rename("ndre")
    return image.addBands(ndre)
