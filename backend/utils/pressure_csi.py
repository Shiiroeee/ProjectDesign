# utils/pressure_csi.py
from __future__ import annotations
import numpy as np

def compute_csi_binary(mask_u8: np.ndarray):
    """
    Minimal binary CSI proxy: area (in pixels) and coverage.
    """
    m = (mask_u8 > 0).astype(np.uint8)
    area = int(m.sum())
    cov = float(m.mean())  # [0..1]
    return float(area), {"area": area, "coverage": cov}

def compute_csi_intensity(
    rgb_crop_u8: np.ndarray,
    mask_u8: np.ndarray,
    strong_tau: float = 0.75,
    weak_tau: float = 0.45,
    gamma: float = 1.2,
):
    """
    Lightweight intensity-based indicator (0..100). We compute masked luminance,
    apply a gamma curve, then scale to 0..100.
    """
    if rgb_crop_u8.dtype != np.uint8:
        rgb = np.clip(rgb_crop_u8, 0, 255).astype(np.uint8)
    else:
        rgb = rgb_crop_u8

    m = (mask_u8 > 0)
    if m.sum() == 0:
        return 0.0, {"mean": 0.0, "coverage": 0.0}

    g = rgb.astype(np.float32) / 255.0
    lum = 0.299 * g[..., 0] + 0.587 * g[..., 1] + 0.114 * g[..., 2]
    lum = np.clip(lum, 0.0, 1.0) ** float(gamma)
    vals = lum[m]

    mean = float(vals.mean() * 100.0)
    info = {"mean": mean, "coverage": float(m.mean()), "strong_tau": strong_tau, "weak_tau": weak_tau}
    return mean, info
