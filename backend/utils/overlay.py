# utils/overlay.py
import base64
import io
import os
from typing import Dict, Optional, Tuple

import cv2
import numpy as np
from PIL import Image


def _largest_component_mask(bw: np.ndarray) -> np.ndarray:
    num, labels, stats, _ = cv2.connectedComponentsWithStats(bw, connectivity=8)
    if num <= 1:
        return bw
    areas = stats[1:, cv2.CC_STAT_AREA]
    idx = 1 + int(areas.argmax())
    return (labels == idx).astype(np.uint8) * 255


def _pca_rotate_upright(mask_u8: np.ndarray) -> np.ndarray:
    ys, xs = np.where(mask_u8 > 0)
    if xs.size < 30:
        return mask_u8

    pts = np.column_stack([xs, ys]).astype(np.float32)
    # OpenCV PCACompute returns (mean, eigenvectors, eigenvalues)
    mean, eigenvectors, _ = cv2.PCACompute2(pts, mean=None)
    vec = eigenvectors[0]  # principal direction
    angle = np.degrees(np.arctan2(vec[1], vec[0]))

    h, w = mask_u8.shape
    M = cv2.getRotationMatrix2D((w / 2.0, h / 2.0), angle - 90.0, 1.0)
    rot = cv2.warpAffine(mask_u8, M, (w, h), flags=cv2.INTER_NEAREST, borderValue=0)
    return rot


def _tight_crop(mask_u8: np.ndarray) -> np.ndarray:
    ys, xs = np.where(mask_u8 > 0)
    if xs.size == 0 or ys.size == 0:
        return mask_u8
    y1, y2 = int(ys.min()), int(ys.max())
    x1, x2 = int(xs.min()), int(xs.max())
    return mask_u8[y1 : y2 + 1, x1 : x2 + 1]


def _compute_csi_from_mask(crop_mask: np.ndarray) -> Tuple[float, int, int, float, float, float]:
    """
    Very simple CSI approximation from a binary mask.
    Returns:
      (csi_percent, forefoot_width_px, arch_width_px, fore_y, arch_y1, arch_y2)
    where y's are normalized in 0..1 over the cropped mask height.
    """
    H, W = crop_mask.shape[:2]
    if H < 3:
        return 0.0, 0, 0, 0.25, 0.30, 0.70

    profile = (crop_mask > 0).sum(axis=1)  # width per row
    fore_band = max(1, int(0.25 * H))
    mid1 = int(0.30 * H)
    mid2 = int(0.70 * H)

    forefoot_width = int(profile[:fore_band].max()) if fore_band > 0 else int(profile.max())
    arch_width = int(profile[mid1:mid2].min()) if mid2 > mid1 else int(profile.min())

    csi = (arch_width / max(forefoot_width, 1)) * 100.0

    foreY = fore_band / float(H)
    archY1 = mid1 / float(H)
    archY2 = mid2 / float(H)

    return float(csi), forefoot_width, arch_width, float(foreY), float(archY1), float(archY2)


def _mask_rgba_data_url(mask_same_size: np.ndarray, alpha: float = 0.40) -> Optional[str]:
    """Convert a mask (0/255) to a white RGBA overlay PNG data URL."""
    if mask_same_size is None:
        return None

    a = (mask_same_size.astype(np.float32) / 255.0) * float(np.clip(alpha, 0.0, 1.0))
    A = (a * 255.0).astype(np.uint8)

    R = np.full_like(A, 255, dtype=np.uint8)
    G = np.full_like(A, 255, dtype=np.uint8)
    B = np.full_like(A, 255, dtype=np.uint8)
    RGBA = np.dstack([R, G, B, A])

    pil = Image.fromarray(RGBA, mode="RGBA")
    buf = io.BytesIO()
    pil.save(buf, format="PNG")
    return "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode("utf-8")


def compute_csi_overlay_for_image(image_path: str, *, include_debug: bool = True) -> Optional[Dict]:
    """
    Fallback CSI+overlay from an IMAGE FILE using Otsu thresholding (no YOLO mask needed).
    Returns:
      {
        "csi": float,
        "overlay": {"fore_y": float, "arch_y1": float, "arch_y2": float},
        "mask_data_url": "data:image/png;base64,...",
        "_debug": {...}   # only if include_debug=True
      }
    """
    if not image_path or not os.path.exists(image_path):
        return None

    img = cv2.imread(image_path)
    if img is None:
        return None

    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    gray = cv2.GaussianBlur(gray, (5, 5), 0)

    # Otsu both polarities; choose larger footprint
    _, bw1 = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    _, bw2 = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)

    m1 = _largest_component_mask(bw1)
    m2 = _largest_component_mask(bw2)

    a1 = int((m1 > 0).sum())
    a2 = int((m2 > 0).sum())
    mask = m1 if a1 >= a2 else m2

    rot = _pca_rotate_upright(mask)
    crop = _tight_crop(rot)

    csi, f_w, a_w, foreY, archY1, archY2 = _compute_csi_from_mask(crop)
    mask_data_url = _mask_rgba_data_url(mask, alpha=0.40)

    out = {
        "csi": float(csi),
        "overlay": {"fore_y": float(foreY), "arch_y1": float(archY1), "arch_y2": float(archY2)},
        "mask_data_url": mask_data_url,
    }

    if include_debug:
        out["_debug"] = {"forefoot_px": int(f_w), "arch_px": int(a_w), "area_px": int((mask > 0).sum())}

    return out
