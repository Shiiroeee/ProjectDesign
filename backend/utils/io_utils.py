# utils/io_utils.py
import io
import base64
from datetime import datetime

import numpy as np
import cv2
from PIL import Image, ImageDraw

from .config import INPUT_SIZE, IMAGENET_RGB_MEAN, GRAYSCALE, RESIZE_MODE, RESIZE_TO_EVAL

try:
    RESAMPLE = Image.Resampling.LANCZOS
except Exception:
    RESAMPLE = Image.LANCZOS


# ----------------------------
# Base64 / Data URL helpers
# ----------------------------
def decode_base64_image(data_url: str) -> Image.Image:
    """Accepts either a full data URL or raw base64; returns RGB PIL image."""
    if "," in data_url:
        data_url = data_url.split(",", 1)[1]
    b = base64.b64decode(data_url)
    return Image.open(io.BytesIO(b)).convert("RGB")


def pil_to_data_url(pil_img: Image.Image) -> str:
    """Encode PIL image as PNG data URL."""
    buf = io.BytesIO()
    pil_img.save(buf, format="PNG")
    return "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode("utf-8")


def encode_png_to_data_url(arr: np.ndarray) -> str:
    """Encode a numpy array (HWC or HW) as PNG data URL."""
    ok, buf = cv2.imencode(".png", arr)
    if not ok:
        raise RuntimeError("PNG encode failed")
    return "data:image/png;base64," + base64.b64encode(buf).decode("utf-8")


def timestamp_filename(prefix: str, ext: str = "png") -> str:
    return f"{prefix}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.{ext}"


# ----------------------------
# Mask / polygon helpers
# ----------------------------
def polygon_to_mask(width: int, height: int, polygon_xy: np.ndarray) -> np.ndarray:
    """Create a binary mask (uint8 0/255) from polygon points."""
    m = np.zeros((height, width), dtype=np.uint8)
    if polygon_xy is not None and len(polygon_xy) >= 3:
        cv2.fillPoly(m, [polygon_xy.astype(np.int32)], 255)
    return m


def draw_poly_or_box_on_pil_crop(crop_pil: Image.Image, polygon_local: np.ndarray, box=None):
    """Debug helper to draw polygon or box on an image."""
    draw = ImageDraw.Draw(crop_pil)
    if polygon_local is not None and len(polygon_local) >= 3:
        pts = [(int(x), int(y)) for x, y in polygon_local]
        draw.line(pts + [pts[0]], fill=(0, 255, 0), width=3)
        r = 3
        for x, y in pts:
            draw.ellipse((x - r, y - r, x + r, y + r), fill=(255, 0, 0))
    elif box is not None:
        bx1, by1, bx2, by2 = box
        draw.rectangle((bx1, by1, bx2, by2), outline=(255, 255, 0), width=3)
    return crop_pil


def apply_mask_rgb(rgb_np: np.ndarray, mask_np: np.ndarray, mode: str) -> np.ndarray:
    """
    Apply a binary mask to an RGB image in 0..255 space (float32 or uint8).
    - mode="mul": hard background removal (black)
    - mode="mean": fill background with ImageNet RGB mean (0..255)
    - mode="none": return original
    """
    if mask_np is None or mode == "none":
        return rgb_np

    m = (mask_np > 127).astype(np.float32)
    m3 = np.stack([m, m, m], axis=-1)

    if mode == "mul":
        return rgb_np * m3

    if mode == "mean":
        bg = np.broadcast_to(IMAGENET_RGB_MEAN.reshape(1, 1, 3), rgb_np.shape)
        return rgb_np * m3 + bg * (1.0 - m3)

    return rgb_np


# ----------------------------
# Resize (match training)
# ----------------------------
def resize_for_model(pil_img: Image.Image) -> np.ndarray:
    """
    MATCHES YOUR v4 EVAL:
      Resize((224,224))  (square)
      (normalize happens later)
    Returns:
      HxWx3 float32 in 0..255
    """
    if GRAYSCALE:
        im = pil_img.convert("L").convert("RGB")
    else:
        im = pil_img.convert("RGB")

    out_w, out_h = int(INPUT_SIZE[0]), int(INPUT_SIZE[1])

    if RESIZE_MODE == "square":
        im = im.resize((out_w, out_h), RESAMPLE)
        arr = np.asarray(im, dtype=np.float32)
        if arr.shape[:2] != (out_h, out_w) or arr.shape[2] != 3:
            raise ValueError(f"Unexpected resized shape: {arr.shape}, expected {(out_h, out_w, 3)}")
        return arr

    # fallback older mode: shorter_side resize + center crop (if you ever switch back)
    if RESIZE_TO_EVAL is None:
        raise ValueError("RESIZE_TO_EVAL is None but RESIZE_MODE!='square'")

    w, h = im.size
    if w <= h:
        new_w, new_h = RESIZE_TO_EVAL, int(round(h * RESIZE_TO_EVAL / w))
    else:
        new_h, new_w = RESIZE_TO_EVAL, int(round(w * RESIZE_TO_EVAL / h))
    im = im.resize((new_w, new_h), RESAMPLE)
    arr = np.asarray(im, dtype=np.float32)

    y0 = max(0, (arr.shape[0] - out_h) // 2)
    x0 = max(0, (arr.shape[1] - out_w) // 2)
    arr = arr[y0:y0 + out_h, x0:x0 + out_w, :]

    if arr.shape[0] != out_h or arr.shape[1] != out_w or arr.shape[2] != 3:
        raise ValueError(f"Center-crop produced unexpected shape: {arr.shape}, expected {(out_h, out_w, 3)}")
    return arr


# ----------------------------
# Mask refinement + tight crop
# ----------------------------
def refine_mask_keep_largest(mask_u8: np.ndarray, ksize: int = 5, close_iters: int = 1) -> np.ndarray:
    """Binarize, close gaps, fill holes, keep largest component. Returns uint8 0/255."""
    if mask_u8.dtype != np.uint8:
        mask_u8 = mask_u8.astype(np.uint8)

    m = (mask_u8 > 0).astype(np.uint8) * 255

    k = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (ksize, ksize))
    if close_iters > 0:
        m = cv2.morphologyEx(m, cv2.MORPH_CLOSE, k, iterations=int(close_iters))

    n, labels, stats, _ = cv2.connectedComponentsWithStats(m, connectivity=8)
    if n > 1:
        areas = [(i, stats[i, cv2.CC_STAT_AREA]) for i in range(1, n)]
        idx = max(areas, key=lambda t: t[1])[0]
        m = np.where(labels == idx, 255, 0).astype(np.uint8)

    h, w = m.shape
    ff = m.copy()
    cv2.floodFill(ff, np.zeros((h + 2, w + 2), np.uint8), (0, 0), 255)
    holes = cv2.bitwise_not(ff)
    m = cv2.bitwise_or(m, holes)

    return m


def tight_crop_image_and_mask(pil_img: Image.Image, mask_u8: np.ndarray, pad: int = 8):
    """Return (cropped_pil_img, cropped_mask) tightly around refined mask."""
    m = refine_mask_keep_largest(mask_u8)

    ys, xs = np.where(m > 0)
    if xs.size == 0 or ys.size == 0:
        return pil_img, mask_u8

    x1, x2 = int(xs.min()), int(xs.max())
    y1, y2 = int(ys.min()), int(ys.max())

    h, w = m.shape
    x1 = max(0, x1 - pad)
    y1 = max(0, y1 - pad)
    x2 = min(w - 1, x2 + pad)
    y2 = min(h - 1, y2 + pad)

    arr = np.array(pil_img.convert("RGB"), dtype=np.uint8)
    arr_c = arr[y1:y2 + 1, x1:x2 + 1, :]
    m_c = m[y1:y2 + 1, x1:x2 + 1]

    pil_c = Image.fromarray(arr_c, mode="RGB")
    return pil_c, m_c
