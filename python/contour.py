"""
Contour Utilities – v2b (HSV-based segmentation + overlay brightening)
--------------------------------------------------------------------------
Optional: Fixed crop (x1, y1, x2, y2) to ignore the background.
Global brightening (alpha/beta) BEFORE the HSV transition.
Configurable HSV threshold to detect the GREEN color of the plant.
Contours drawn in **green** (0, 255, 0) then saved:
contour_overlays/<basename>_full.jpg (full image brightened)
contour_overlays/<basename>_crop.jpg (crop area brightened)
"""

from __future__ import annotations
import cv2, numpy as np, os
from pathlib import Path
from typing import Tuple, Optional, Dict

# ─────────────────────────── Global Settings ───────────────────────────
OVERLAY_DIR = "contour_overlays"
Path(OVERLAY_DIR).mkdir(exist_ok=True)

# Default parameters (modifiable on call)
DEFAULT_CROP   : Optional[Tuple[int, int, int, int]] = None  # (x1, y1, x2, y2)
DEFAULT_ALPHA  : float = 1.4   # contraste
DEFAULT_BETA   : int   = 40    # luminosité
DEFAULT_LOWER_GREEN = np.array([33, 85, 60])
DEFAULT_UPPER_GREEN = np.array([90, 255, 255])
MIN_AREA_THRESHOLD = 300

__all__ = ["process_and_save"]

# ────────────────────────────────────────────────────────────────────────

def _segment_green(img_bgr: np.ndarray,
                   lower_green: np.ndarray,
                   upper_green: np.ndarray) -> np.ndarray:
    """Returns a binary mask of the green areas (already brightened image)."""
    hsv  = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2HSV)
    mask = cv2.inRange(hsv, lower_green, upper_green)

    kernel = np.ones((5, 5), np.uint8)
    mask   = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel)
    mask   = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel)
    return mask

# ────────────────────────────────────────────────────────────────────────

def process_and_save(
    img_path: str,
    *,
    crop: Optional[Tuple[int, int, int, int]] = DEFAULT_CROP,
    alpha: float = DEFAULT_ALPHA,
    beta: int   = DEFAULT_BETA,
    lower_green: np.ndarray = DEFAULT_LOWER_GREEN,
    upper_green: np.ndarray = DEFAULT_UPPER_GREEN,
) -> Dict[str, str | int]:
    """Parses `img_path`, generates two overlays and returns a summary."""
    img = cv2.imread(img_path)
    if img is None:
        raise FileNotFoundError(img_path)

    # ───── Brightening global ───────────────────────────────────────────
    bright = cv2.convertScaleAbs(img, alpha=alpha, beta=beta)

    # ───── Crop (optional) ────────────────────────────────────────────
    if crop:
        x1, y1, x2, y2 = crop
        cropped = bright[y1:y2, x1:x2]
    else:
        cropped = bright
        x1 = y1 = 0  # used for further reprojection

    # ───── Green mask────────────────────────────────────────────────
    mask = _segment_green(cropped, lower_green, upper_green)

    # ───── Filtered contours ───────────────────────────────────────────
    cnts, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    cnts    = [c for c in cnts if cv2.contourArea(c) > MIN_AREA_THRESHOLD]
    area_px = int(sum(cv2.contourArea(c) for c in cnts))

    # ───── Drawing overlays (on brightened image) ─────────────────────
    crop_overlay = cropped.copy()
    cv2.drawContours(crop_overlay, cnts, -1, (0, 0, 255), 5)

    full_overlay = bright.copy()
    if crop and cnts:
        offset     = np.array([[x1, y1]])
        cnts_full  = [c + offset for c in cnts]
        cv2.drawContours(full_overlay, cnts_full, -1, (0, 0, 255), 5)
    else:
        cv2.drawContours(full_overlay, cnts, -1, (0, 0, 255), 5)

    # ───── Save file ────────────────────────────────────────
    base       = os.path.splitext(os.path.basename(img_path))[0]
    crop_out   = os.path.join(OVERLAY_DIR, f"{base}_crop.jpg")
    full_out   = os.path.join(OVERLAY_DIR, f"{base}_full.jpg")

    cv2.imwrite(crop_out, crop_overlay)
    cv2.imwrite(full_out, full_overlay)

    return {
        "original"    : os.path.basename(img_path),
        "overlay_crop": crop_out,
        "overlay_full": full_out,
        "area_px"     : area_px,
    }