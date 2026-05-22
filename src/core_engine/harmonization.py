"""
Spectral harmonization and band standardization [FR-04].

Harmonization (Landsat only):
  Apply Roy et al. (2016) linear coefficients to Red and NIR bands to make
  Landsat 8/9 reflectance spectrally consistent with Sentinel-2.

  Coefficients (Landsat 8 → Sentinel-2 equivalent):
    Red: adjusted = original * 1.0536 + (−0.0049)
    NIR: adjusted = original * 1.0740 + (−0.0102)

  Source: Roy et al. (2016) "Characterization of Landsat-7 to Landsat-8
  reflective wavelength and normalized difference vegetation index continuity"
  Remote Sensing of Environment, DOI: 10.1016/j.rse.2015.12.024

  Applied BEFORE index calculation, AFTER scaling to [0,1] reflectance.
  Only Red and NIR are adjusted — no other bands modified (Spectral Preservation rule).

Band standardization:
  Both sensors are mapped to unified band names after scaling to [0,1]:
    S2 (÷10000):           B2→blue, B3→green, B4→red, B5→red_edge, B8→nir,  B11→swir1, B12→swir2
    Landsat C2 (×0.0000275 − 0.2): SR_B2→blue, SR_B3→green, SR_B4→red, SR_B5→nir, SR_B6→swir1, SR_B7→swir2

  Note: Landsat has no red_edge band (B5 on Landsat maps to NIR, not Red Edge).
  NDRE is not computable from Landsat; that is handled in index_calculator.py.
"""

from __future__ import annotations

import ee

# ---------------------------------------------------------------------------
# Band mapping tables
# ---------------------------------------------------------------------------

# Sentinel-2 SR Harmonized — relevant optical bands
_S2_BANDS_IN  = ["B2",    "B3",    "B4",  "B5",        "B8",  "B11",  "B12"]
_S2_BANDS_OUT = ["blue", "green", "red", "red_edge",  "nir", "swir1", "swir2"]

# Landsat 8/9 C2 T1 Level-2 — surface reflectance bands
_LS_BANDS_IN  = ["SR_B2", "SR_B3",  "SR_B4", "SR_B5", "SR_B6",  "SR_B7"]
_LS_BANDS_OUT = ["blue",  "green",  "red",   "nir",   "swir1",  "swir2"]

# Landsat C2 T1_L2 surface reflectance scale factors (applied to DN to get [0,1])
_LS_SR_SCALE  =  0.0000275
_LS_SR_OFFSET = -0.2

# Roy et al. (2016): Landsat 8 → Sentinel-2 spectral harmonization coefficients.
# Applied to [0,1] surface reflectance values for Red and NIR bands ONLY.
# Reference: Roy et al. (2016), RSE, DOI: 10.1016/j.rse.2015.12.024
_ROY_RED_SLOPE     = 1.0536
_ROY_RED_INTERCEPT = -0.0049
_ROY_NIR_SLOPE     = 1.0740
_ROY_NIR_INTERCEPT = -0.0102


def prepare_image(image: ee.Image, sensor: str) -> ee.Image:
    """
    Scale reflectance bands to [0,1], standardize band names, and apply
    Roy et al. (2016) harmonization to Landsat Red and NIR bands.

    Pipeline order:
      1. Select relevant optical bands.
      2. Scale to [0,1] surface reflectance.
      3. Rename to standard band names.
      4. (Landsat only) Apply Roy harmonization to Red and NIR.

    Args:
        image:  Cloud-masked satellite image (original GEE collection bands).
        sensor: "S2", "L8", or "L9".

    Returns:
        Image with standardized [0,1] reflectance bands.
        Landsat Red/NIR are harmonized to S2 spectral equivalents.

    Raises:
        ValueError: If sensor is not one of "S2", "L8", "L9".
    """
    if sensor == "S2":
        return _prepare_s2(image)
    elif sensor in ("L8", "L9"):
        return _prepare_landsat(image)
    else:
        raise ValueError(f"Unknown sensor: {sensor!r}. Expected 'S2', 'L8', or 'L9'.")


# ---------------------------------------------------------------------------
# Sensor-specific preparation
# ---------------------------------------------------------------------------

def _prepare_s2(image: ee.Image) -> ee.Image:
    """
    Scale S2 bands to [0,1] reflectance and rename to standard names.
    No harmonization needed — S2 is the reference sensor.
    """
    return (
        image
        .select(_S2_BANDS_IN)
        .divide(10000)
        .rename(_S2_BANDS_OUT)
    )


def _prepare_landsat(image: ee.Image) -> ee.Image:
    """
    Scale Landsat bands to [0,1] surface reflectance, rename to standard
    names, then apply Roy et al. (2016) harmonization to Red and NIR.

    Scaling formula: reflectance = DN * 0.0000275 + (−0.2)
    Roy coefficients: adjusted = original * slope + intercept
    """
    # Step 1: Scale DN to [0,1] surface reflectance and rename bands
    scaled = (
        image
        .select(_LS_BANDS_IN)
        .multiply(_LS_SR_SCALE)
        .add(_LS_SR_OFFSET)
        .rename(_LS_BANDS_OUT)
    )

    # Step 2: Apply Roy et al. (2016) harmonization to Red and NIR ONLY.
    # These coefficients map Landsat 8/9 spectral response to Sentinel-2 equivalent.
    # Source: Roy et al. (2016), RSE, DOI: 10.1016/j.rse.2015.12.024
    red_harmonized = (
        scaled.select("red")
        .multiply(_ROY_RED_SLOPE)
        .add(_ROY_RED_INTERCEPT)
        .rename("red")
    )
    nir_harmonized = (
        scaled.select("nir")
        .multiply(_ROY_NIR_SLOPE)
        .add(_ROY_NIR_INTERCEPT)
        .rename("nir")
    )

    # Replace original red/nir bands with harmonized versions (all other bands unchanged)
    return scaled.addBands([red_harmonized, nir_harmonized], overwrite=True)
