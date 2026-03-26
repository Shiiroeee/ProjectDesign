# backend/utils/detect.py
from __future__ import annotations

import os, re
import numpy as np
import cv2
from PIL import Image
from ultralytics import YOLO

from .config import (
    DETECTOR_PATH,
    DETECTOR_IMG_DEFAULT,
    DETECTOR_CLASS_NAMES_OVERRIDE,  # ✅ now used
)

# --------------------------------------------------------------------
# Keep inference on CPU on Windows for stability (ONLY on Windows)
# --------------------------------------------------------------------
if os.name == "nt":
    os.environ.setdefault("CUDA_VISIBLE_DEVICES", "")
    os.environ.setdefault("ORT_DML_ENABLE_GPU_FALLBACK", "0")

# --------------------------------------------------------------------
# Helpers to robustly load weights
# --------------------------------------------------------------------
def _is_lfs_pointer(path: str) -> bool:
    """Return True if file is a Git LFS pointer, not the real binary."""
    try:
        with open(path, "rb") as f:
            head = f.read(128)
        return head.startswith(b"version https://git-lfs.github.com/spec/v1")
    except Exception:
        return False

def _validate_weights_path(path: str) -> None:
    """Early validation to surface clear, actionable errors."""
    if not path or not os.path.exists(path):
        raise FileNotFoundError(f"Model weights not found: {path!r}")

    lower = str(path).lower()
    if lower.endswith((".yaml", ".yml")):
        raise ValueError(
            f"You passed a YAML architecture file for inference:\n  {path}\n"
            f"Use a trained weights file (.pt or .safetensors), or an exported runtime (.onnx/.engine)."
        )

    if _is_lfs_pointer(path):
        raise ValueError(
            f"File looks like a Git LFS pointer (not real weights):\n  {path}\n"
            f"Run these in your repo:\n"
            f"  git lfs install\n"
            f"  git lfs pull\n"
        )

def _load_yolo(path: str, task_hint: str = "segment"):
    """
    Robust loader:
    - validates path / LFS / YAML
    - tries the provided task_hint (segment by default)
    - falls back to 'detect' if needed
    - lets Ultralytics auto-pick backend for .onnx/.engine
    """
    _validate_weights_path(path)

    try:
        return YOLO(path, task=task_hint)
    except Exception as e1:
        if task_hint != "detect":
            try:
                return YOLO(path, task="detect")
            except Exception as e2:
                raise RuntimeError(
                    "Failed to load YOLO weights.\n"
                    f"  path: {path}\n"
                    f"  first attempt (task={task_hint}) error: {e1}\n"
                    f"  fallback (task=detect) error: {e2}"
                ) from e2
        raise RuntimeError(
            f"Failed to load YOLO weights (task={task_hint}).\n  path: {path}\n  error: {e1}"
        ) from e1

# --------------------------------------------------------------------
# Create global detector (prefer CPU on Windows; otherwise allow default)
# --------------------------------------------------------------------
detector = _load_yolo(DETECTOR_PATH, task_hint="segment")

# --------------------------------------------------------------------
# Image size auto-detection from backend session (for ONNX/engine)
# --------------------------------------------------------------------
def _auto_imgsz_from_backend(yolo_obj) -> int:
    try:
        backend = getattr(yolo_obj, "model", None)
        session = getattr(backend, "session", None)
        if session:
            shape = session.get_inputs()[0].shape  # typically [N,3,H,W]
            h = shape[2] if isinstance(shape[2], int) else None
            w = shape[3] if isinstance(shape[3], int) else None
            if h and w and h == w:
                return int(h)
    except Exception:
        pass
    return int(DETECTOR_IMG_DEFAULT)

DETECTOR_IMG = _auto_imgsz_from_backend(detector)

# --------------------------------------------------------------------
# Predict wrapper with graceful imgsz fallback
# --------------------------------------------------------------------
_EXPECT_PATTERNS = [
    r"Expected:\s*(\d+)",
    r"expected\s*(\d+)",
    r"input.*?(\d{3,4}).*?(\d{3,4})",  # sometimes shows H W
]

def _extract_expected_imgsz(err_text: str):
    for pat in _EXPECT_PATTERNS:
        m = re.findall(pat, err_text, flags=re.IGNORECASE)
        if not m:
            continue
        # m can be list of strings or tuples
        first = m[0]
        if isinstance(first, tuple):
            # pick first numeric in tuple
            for v in first:
                if str(v).isdigit():
                    return int(v)
        if str(first).isdigit():
            return int(first)
    return None

def _run_yolo(pil_image: Image.Image, imgsz: int, conf: float, want_masks: bool):
    try:
        return detector.predict(
            source=pil_image,
            imgsz=imgsz,
            conf=conf,
            retina_masks=bool(want_masks),
            device="cpu" if os.name == "nt" else None,  # ✅ CPU on Windows; default elsewhere
            verbose=False,
        )[0]
    except RuntimeError as e:
        expected = _extract_expected_imgsz(str(e))
        if expected:
            return detector.predict(
                source=pil_image,
                imgsz=expected,
                conf=conf,
                retina_masks=bool(want_masks),
                device="cpu" if os.name == "nt" else None,
                verbose=False,
            )[0]
        raise

# --------------------------------------------------------------------
# Class normalization (to Left/Right/Unknown)
# --------------------------------------------------------------------
def _norm_class(name) -> str:
    s = str(name or "").strip().lower()
    if s in {"left", "l", "lf", "left_foot"}:
        return "Left"
    if s in {"right", "r", "rt", "right_foot"}:
        return "Right"
    return "Unknown"

def _resolve_names(res) -> dict:
    """
    Prefer:
      1) DETECTOR_CLASS_NAMES_OVERRIDE (if provided)
      2) res.names
      3) detector.names
    """
    names = {}
    try:
        if isinstance(DETECTOR_CLASS_NAMES_OVERRIDE, dict) and DETECTOR_CLASS_NAMES_OVERRIDE:
            names.update({int(k): str(v) for k, v in DETECTOR_CLASS_NAMES_OVERRIDE.items()})
    except Exception:
        pass

    try:
        rn = getattr(res, "names", None)
        if isinstance(rn, dict) and rn:
            names.update(rn)
    except Exception:
        pass

    try:
        dn = getattr(detector, "names", None)
        if isinstance(dn, dict) and dn:
            names.update(dn)
    except Exception:
        pass

    return names

# --------------------------------------------------------------------
# Public API
# --------------------------------------------------------------------
def extract_instances_with_polys(pil_image: Image.Image, conf: float = 0.30):
    """
    Run detection/segmentation on a PIL Image and return list of instances with:
      - bounding box (x1,y1,x2,y2)
      - normalized class ("Left"/"Right"/"Unknown")
      - confidence
      - has_mask flag
      - polygon_global (np.int32 Nx2)
    """
    W, H = pil_image.size

    # Ask for masks; if model is detect-only, masks will be None and we fall back to boxes.
    res = _run_yolo(pil_image, imgsz=DETECTOR_IMG, conf=conf, want_masks=True)

    out = []
    if res is None or getattr(res, "boxes", None) is None or len(res.boxes) == 0:
        return out

    names = _resolve_names(res)

    for j in range(len(res.boxes)):
        b = res.boxes[j]

        x1, y1, x2, y2 = map(int, b.xyxy[0].tolist())
        x1 = max(0, min(x1, W - 1)); x2 = max(1, min(x2, W))
        y1 = max(0, min(y1, H - 1)); y2 = max(1, min(y2, H))
        if x2 <= x1 or y2 <= y1:
            continue

        confj = float(b.conf[0]) if getattr(b, "conf", None) is not None else 0.0
        clsid = int(b.cls[0]) if getattr(b, "cls", None) is not None else -1
        raw_name = names.get(clsid, "Unknown")
        cname = _norm_class(raw_name)

        poly = None
        has_mask = False
        masks = getattr(res, "masks", None)

        if masks is not None:
            xy = getattr(masks, "xy", None)

            # Prefer polygon from masks.xy (vector masks)
            if xy is not None and len(xy) > j and xy[j] is not None:
                parts = xy[j] if isinstance(xy[j], (list, tuple)) else [xy[j]]
                best, best_a = None, 0.0
                for part in parts:
                    p = np.array(part, dtype=np.float32).reshape(-1, 2)
                    if len(p) >= 3:
                        a = cv2.contourArea(p)
                        if a > best_a:
                            best_a, best = a, p
                if best is not None:
                    poly = np.round(best).astype(np.int32)
                    has_mask = True

            # Fallback: raster mask -> contour
            if poly is None and getattr(masks, "data", None) is not None:
                try:
                    m = masks.data[j].cpu().numpy().squeeze()
                    m8 = (m * 255).astype(np.uint8)
                    cnts, _ = cv2.findContours(m8, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
                    if cnts:
                        c = max(cnts, key=cv2.contourArea)
                        poly = c.reshape(-1, 2).astype(np.int32)
                        has_mask = True
                except Exception:
                    poly = None

        # If no mask, fall back to the box polygon
        if poly is None:
            poly = np.array([[x1, y1], [x2, y1], [x2, y2], [x1, y2]], dtype=np.int32)

        out.append({
            "x1": x1, "y1": y1, "x2": x2, "y2": y2,
            "conf": confj,
            "cls_id": clsid,
            "class": cname,
            "polygon_global": poly,
            "has_mask": has_mask,
        })

    return out
