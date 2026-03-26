# utils/pipeline.py
from __future__ import annotations

import math
import numpy as np
import cv2
from PIL import Image

from .detect import extract_instances_with_polys
from .io_utils import (
    decode_base64_image,
    pil_to_data_url,
    polygon_to_mask,
    encode_png_to_data_url,
    tight_crop_image_and_mask,
)
from .classify import classify_with_mask
from .pressure_csi import compute_csi_intensity, compute_csi_binary

from .config import (
    CSI_TRIM_TOP_FRAC, CSI_TRIM_BOTTOM_FRAC,
    CSI_FOREFOOT_TOP_FRAC, CSI_FOREFOOT_HEIGHT_FRAC,
    CSI_ARCH_TOP_FRAC, CSI_ARCH_BOTTOM_FRAC,
    CSI_BAND_HALF_FRAC, CSI_MORPH_KERNEL, CSI_MORPH_CLOSE_ITERS,
)

# ================================
# Option B: simplest decision rule
# (pure argmax over probabilities)
# ================================
def choose_arch_label(prob: dict) -> str:
    p = dict(prob or {})
    p.setdefault("Flat", 0.0)
    p.setdefault("Normal", 0.0)
    p.setdefault("High", 0.0)
    return max(p, key=p.get)

# ================================
# Helpers
# ================================
def _poly_to_ndarray(poly):
    if poly is None:
        return None
    if isinstance(poly, np.ndarray):
        if poly.ndim >= 2 and poly.shape[-1] == 2:
            return poly.astype(np.int32)
        return None
    if isinstance(poly, list) and len(poly) >= 3:
        try:
            return np.array(poly, dtype=np.int32).reshape(-1, 2)
        except Exception:
            return None
    return None

def _poly_to_list(poly):
    if poly is None:
        return []
    if isinstance(poly, list):
        out = []
        for p in poly:
            if isinstance(p, (list, tuple)) and len(p) == 2:
                out.append([int(p[0]), int(p[1])])
        return out
    if isinstance(poly, np.ndarray):
        return poly.reshape(-1, 2).astype(np.int32).tolist()
    return []

def _tight_crop_rgba_by_mask(crop_pil: Image.Image, mask_u8: np.ndarray) -> Image.Image:
    arr = np.array(crop_pil)
    if arr.ndim == 2:
        arr = np.dstack([arr, arr, arr])
    if arr.shape[2] == 4:
        arr = arr[:, :, :3]

    alpha = mask_u8.copy()
    if alpha.max() <= 1:
        alpha = (alpha * 255).astype(np.uint8)

    rgba = np.dstack([arr, alpha])
    ys, xs = np.where(alpha > 0)
    if len(xs) == 0 or len(ys) == 0:
        return Image.fromarray(rgba, mode="RGBA")

    x_min, x_max = xs.min(), xs.max() + 1
    y_min, y_max = ys.min(), ys.max() + 1
    rgba_tight = rgba[y_min:y_max, x_min:x_max, :]
    return Image.fromarray(rgba_tight, mode="RGBA")

def _norm_name(name: str) -> str:
    return str(name or "").strip().lower()

def _bbox_area(x1, y1, x2, y2):
    return max(0, x2 - x1) * max(0, y2 - y1)

def _iou(box_a, box_b):
    ax1, ay1, ax2, ay2 = box_a
    bx1, by1, bx2, by2 = box_b
    ix1, iy1 = max(ax1, bx1), max(ay1, by1)
    ix2, iy2 = min(ax2, bx2), min(ay2, by2)
    iw, ih = max(0, ix2 - ix1), max(0, iy2 - iy1)
    inter = iw * ih
    ua = _bbox_area(*box_a)
    ub = _bbox_area(*box_b)
    union = ua + ub - inter
    return inter / union if union > 0 else 0.0

def _polygon_area_xy(pg_list):
    if not isinstance(pg_list, list) or len(pg_list) < 3:
        return 0.0
    x = np.array([p[0] for p in pg_list], dtype=np.float32)
    y = np.array([p[1] for p in pg_list], dtype=np.float32)
    return float(0.5 * abs(np.dot(x, np.roll(y, -1)) - np.dot(y, np.roll(x, -1))))

def _fill_ratio_global(pg_list, x1, y1, x2, y2):
    box_a = _bbox_area(x1, y1, x2, y2)
    if box_a <= 0:
        return 0.0
    if not isinstance(pg_list, list) or len(pg_list) < 3:
        return 1.0
    return max(0.0, min(1.0, _polygon_area_xy(pg_list) / box_a))

def _clip(v, lo, hi):
    return max(lo, min(hi, v))

def _expand_box(x1, y1, x2, y2, W, H, pad_ratio=0.10, make_square=True):
    w = (x2 - x1)
    h = (y2 - y1)
    if w <= 0 or h <= 0:
        return x1, y1, x2, y2

    cx = x1 + w / 2.0
    cy = y1 + h / 2.0

    if make_square:
        side = max(w, h) * (1.0 + 2 * pad_ratio)
        nw = nh = side
    else:
        nw = w * (1.0 + 2 * pad_ratio)
        nh = h * (1.0 + 2 * pad_ratio)

    nx1 = int(round(cx - nw / 2.0))
    nx2 = int(round(cx + nw / 2.0))
    ny1 = int(round(cy - nh / 2.0))
    ny2 = int(round(cy + nh / 2.0))

    nx1 = _clip(nx1, 0, W - 1)
    nx2 = _clip(nx2, 1, W)
    ny1 = _clip(ny1, 0, H - 1)
    ny2 = _clip(ny2, 1, H)
    if nx2 <= nx1 + 1: nx2 = min(W, nx1 + 2)
    if ny2 <= ny1 + 1: ny2 = min(H, ny1 + 2)
    return nx1, ny1, nx2, ny2

def _crop_image_and_mask(pil_image: Image.Image, box_xyxy, polygon_global):
    W, H = pil_image.size
    x1, y1, x2, y2 = box_xyxy
    ex1, ey1, ex2, ey2 = _expand_box(x1, y1, x2, y2, W, H, pad_ratio=0.10, make_square=True)

    crop = pil_image.crop((ex1, ey1, ex2, ey2))
    cw, ch = crop.size

    pg_nd = _poly_to_ndarray(polygon_global)
    if pg_nd is None or len(pg_nd) < 3:
        pg_nd = np.array([[ex1, ey1], [ex2, ey1], [ex2, ey2], [ex1, ey2]], dtype=np.int32)

    g = pg_nd.astype(np.int32).copy()
    g[:, 0] = np.clip(g[:, 0] - ex1, 0, cw - 1)
    g[:, 1] = np.clip(g[:, 1] - ey1, 0, ch - 1)
    poly_local = g

    mask_local = polygon_to_mask(cw, ch, poly_local)
    return crop, mask_local, _poly_to_list(poly_local), (ex1, ey1, ex2, ey2)

# ================================
# CSI helpers
# ================================
def _upright_mask(mask_u8: np.ndarray) -> np.ndarray:
    """Rotate the binary mask so heel→toe axis is vertical using PCA."""
    m = (mask_u8 > 127).astype(np.uint8)
    ys, xs = np.where(m > 0)
    if xs.size < 30:
        return (m * 255).astype(np.uint8)
    pts = np.column_stack([xs.astype(np.float32), ys.astype(np.float32)])
    mu = pts.mean(axis=0, keepdims=True)
    X = pts - mu
    cov = (X.T @ X) / max(len(X) - 1, 1)
    eigvals, eigvecs = np.linalg.eigh(cov)
    v = eigvecs[:, 1]
    theta = math.degrees(math.atan2(v[1], v[0]))
    rot_deg = 90.0 - theta
    h, w = m.shape
    M = cv2.getRotationMatrix2D((w / 2.0, h / 2.0), rot_deg, 1.0)
    mr = cv2.warpAffine(m, M, (w, h), flags=cv2.INTER_NEAREST, borderValue=0)
    return (mr > 0).astype(np.uint8) * 255

def _dynamic_csi_from_mask(mask_u8: np.ndarray):
    m = mask_u8.astype(np.uint8).copy()
    m = (m > 127).astype(np.uint8) * 255

    ksz = max(3, int(CSI_MORPH_KERNEL)) | 1
    k = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (ksz, ksz))
    m = cv2.morphologyEx(m, cv2.MORPH_CLOSE, k, iterations=int(CSI_MORPH_CLOSE_ITERS))

    H, W = m.shape[:2]
    rows = np.where(m.max(axis=1) > 0)[0]
    if rows.size == 0:
        return 0.0, {"fore_y": 0.25, "arch_y1": 0.30, "arch_y2": 0.70}

    y_min, y_max = int(rows.min()), int(rows.max())
    h = max(1, y_max - y_min + 1)

    trim_top = int(round(CSI_TRIM_TOP_FRAC * h))
    trim_bot = int(round(CSI_TRIM_BOTTOM_FRAC * h))
    y_min_adj = min(y_max, y_min + trim_top)
    y_max_adj = max(y_min_adj, y_max - trim_bot)
    h_adj = max(1, y_max_adj - y_min_adj + 1)

    xs = np.argmax(m > 0, axis=1)
    xe = W - np.argmax(np.flip(m > 0, axis=1), axis=1) - 1
    row_has = (m > 0).any(axis=1)
    width = np.where(row_has, (xe - xs + 1).clip(min=0), 0)

    ff_top = y_min_adj + int(round(CSI_FOREFOOT_TOP_FRAC * h_adj))
    ff_bot = min(y_max_adj, ff_top + int(round(CSI_FOREFOOT_HEIGHT_FRAC * h_adj)))
    ff_slice = slice(ff_top, ff_bot + 1)
    fore_row = ff_top if ff_bot <= ff_top else ff_top + int(np.argmax(width[ff_slice]))
    fore_w = max(1, int(width[fore_row]))

    arch_top = y_min_adj + int(round(CSI_ARCH_TOP_FRAC * h_adj))
    arch_bot = y_min_adj + int(round(CSI_ARCH_BOTTOM_FRAC * h_adj))
    arch_top = max(arch_top, y_min_adj)
    arch_bot = min(arch_bot, y_max_adj)
    arch_slice = slice(arch_top, arch_bot + 1)

    if arch_bot <= arch_top:
        arch_row = arch_top
    else:
        sub_w = width[arch_slice]
        sub_w_pos = np.where(sub_w > 0, sub_w, np.inf)
        rel = int(np.argmin(sub_w_pos))
        arch_row = arch_top + rel
        if not np.isfinite(sub_w_pos[rel]):
            arch_row = (arch_top + arch_bot) // 2
    arch_w = max(1, int(width[arch_row]))

    csi = (arch_w / fore_w) * 100.0

    half = max(2, int(round(CSI_BAND_HALF_FRAC * H)))
    y1 = int(np.clip(arch_row - half, 0, H - 1))
    y2 = int(np.clip(arch_row + half, 0, H - 1))

    fore_y  = (fore_row + 0.5) / H
    arch_y1 = y1 / H
    arch_y2 = y2 / H

    return float(csi), {"fore_y": float(fore_y), "arch_y1": float(arch_y1), "arch_y2": float(arch_y2)}

def _arch_from_csi(csi: float) -> str:
    if csi < 25.0:
        return "High"
    if csi > 45.0:
        return "Flat"
    return "Normal"

# ================================
# Optional CSI soft prior
# ================================
def _apply_soft_prior(probs: dict, csi_val: float) -> dict:
    P = dict(probs or {})
    P.setdefault("Flat", 0.0)
    P.setdefault("Normal", 0.0)
    P.setdefault("High", 0.0)

    if csi_val >= 60.0:
        P["Flat"]   *= 1.20
        P["Normal"] *= 0.90
    elif csi_val <= 35.0:
        P["High"]   *= 1.20
        P["Normal"] *= 0.95

    s = float(sum(P.values()))
    if s > 0:
        for k in P:
            P[k] /= s
    return P

# ================================
# Detect API
# ================================
def detect_instances(b64_image: str):
    pil_image = decode_base64_image(b64_image)
    W, H = pil_image.size
    mid_x = W / 2.0

    raw = extract_instances_with_polys(pil_image, conf=0.30)

    MIN_AREA_FRAC = 0.003
    raw = [d for d in raw if _bbox_area(d["x1"], d["y1"], d["x2"], d["y2"]) >= MIN_AREA_FRAC * (W * H)]

    if not raw:
        return {"status": "ok", "boxes": [], "detections": []}

    items = []
    for d in raw:
        cname = _norm_name(d.get("class"))
        if cname in {"left", "l", "left_foot"}:
            cls = "Left"
        elif cname in {"right", "r", "right_foot"}:
            cls = "Right"
        else:
            cls = "Unknown"

        pg = d.get("polygon_global")
        if isinstance(pg, np.ndarray):
            pg = pg.reshape(-1, 2).astype(np.int32).tolist()

        items.append({
            "x1": int(d["x1"]), "y1": int(d["y1"]), "x2": int(d["x2"]), "y2": int(d["y2"]),
            "conf": float(d.get("conf", 0.0)),
            "class": cls,
            "polygon_global": pg or [],
        })

    LR_CONF_MIN = 0.30
    FILL_MIN = 0.25

    unknowns = [it for it in items if it["class"] == "Unknown"]
    lr_cands = []
    for it in (i for i in items if i["class"] in {"Left", "Right"}):
        fill = _fill_ratio_global(it["polygon_global"], it["x1"], it["y1"], it["x2"], it["y2"])
        if it["conf"] >= LR_CONF_MIN and fill >= FILL_MIN:
            lr_cands.append(it)

    UNKNOWN_OVERRIDE_IOU = 0.30
    def blocked_by_unknown(it):
        box = (it["x1"], it["y1"], it["x2"], it["y2"])
        for u in unknowns:
            if _iou(box, (u["x1"], u["y1"], u["x2"], u["y2"])) >= UNKNOWN_OVERRIDE_IOU:
                return True
        return False

    lr_kept = [it for it in lr_cands if not blocked_by_unknown(it)]
    boxes = unknowns + lr_kept

    for it in lr_kept:
        cx = 0.5 * (it["x1"] + it["x2"])
        it["side"] = "Left" if cx < mid_x else "Right"
        it["area"] = _bbox_area(it["x1"], it["y1"], it["x2"], it["y2"])

    lefts  = sorted((d for d in lr_kept if d["side"] == "Left"),
                    key=lambda z: (z["area"] * z.get("conf", 0.0)), reverse=True)
    rights = sorted((d for d in lr_kept if d["side"] == "Right"),
                    key=lambda z: (z["area"] * z.get("conf", 0.0)), reverse=True)

    selected = []
    if lefts:  selected.append(lefts[0])
    if rights: selected.append(rights[0])

    detections = []
    for d in selected:
        crop_pil, mask_local, poly_local, (ex1, ey1, ex2, ey2) = _crop_image_and_mask(
            pil_image,
            (d["x1"], d["y1"], d["x2"], d["y2"]),
            d.get("polygon_global"),
        )

        segmented_rgba = _tight_crop_rgba_by_mask(crop_pil, mask_local)
        seg_du = pil_to_data_url(segmented_rgba)

        detections.append({
            "x1": ex1, "y1": ey1, "x2": ex2, "y2": ey2,
            "class": "foot",
            "side": d["side"],
            "cropped_image": seg_du,
            "annotated_cropped": seg_du,
            "polygon": poly_local,
            "polygon_applied": True
        })

    def _order(b):
        c = b["class"]
        if c == "Left": return (0, -b["conf"])
        if c == "Right": return (1, -b["conf"])
        return (2, -b["conf"])

    boxes = sorted(boxes, key=_order)
    detections.sort(key=lambda k: (0 if k["side"] == "Left" else 1))

    return {"status": "ok", "boxes": boxes, "detections": detections}

# ================================
# Classify endpoints
# ================================
def classify_crop(b64_image: str, polygon=None):
    pil_img_full = decode_base64_image(b64_image)
    Wc, Hc = pil_img_full.size

    if isinstance(polygon, list) and len(polygon) >= 3:
        pts = np.array(polygon, dtype=np.int32).reshape(-1, 2)
        mask_full = polygon_to_mask(Wc, Hc, pts)
    else:
        mask_full = np.ones((Hc, Wc), dtype=np.uint8) * 255

    pil_tight, mask_tight = tight_crop_image_and_mask(pil_img_full, mask_full, pad=8)
    rgb_tight = np.array(pil_tight.convert("RGB"), dtype=np.uint8)

    # CSI (upright mask)
    mask_upright = _upright_mask(mask_tight)
    csi_dyn, overlay = _dynamic_csi_from_mask(mask_upright)
    csi_arch = _arch_from_csi(csi_dyn)

    # legacy CSI (optional)
    icsi, info_i = compute_csi_intensity(rgb_tight, mask_tight, strong_tau=0.75, weak_tau=0.45, gamma=1.2)
    csi_bin, info_b = compute_csi_binary(mask_tight)

    # model probs (API order)
    _label0, _conf0, probs0 = classify_with_mask(pil_tight, mask_tight, mask_mode="mean")

    # optional CSI prior
    probs = _apply_soft_prior(probs0, csi_dyn)

    # ✅ Option B final decision (argmax)
    label = choose_arch_label(probs)
    conf = float(probs.get(label, 0.0))

    return {
        "prediction": label,
        "confidence": conf,
        "probabilities": probs,
        "csi_intensity": icsi,
        "csi_binary": csi_bin,
        "csi_info": {"intensity": info_i, "binary": info_b},
        "overlay": overlay,
        "csi": float(csi_dyn),
        "csi_arch": csi_arch,
        "mask_overlay": encode_png_to_data_url(mask_tight),
    }

def process_end_to_end(b64_image: str, save: bool = False):
    det_payload = detect_instances(b64_image)
    if det_payload.get("status") != "ok":
        return det_payload

    detections = det_payload.get("detections", [])
    out = []

    for det in detections:
        crop = decode_base64_image(det["cropped_image"])
        cw, ch = crop.size
        poly = det.get("polygon") or []
        poly_np = np.array(poly, dtype=np.int32).reshape(-1, 2) if len(poly) >= 3 else None
        mask = polygon_to_mask(cw, ch, poly_np) if poly_np is not None else np.ones((ch, cw), dtype=np.uint8) * 255

        pil_tight, mask_tight = tight_crop_image_and_mask(crop, mask, pad=8)
        rgb_tight = np.array(pil_tight.convert("RGB"), dtype=np.uint8)

        mask_upright = _upright_mask(mask_tight)
        csi_dyn, overlay = _dynamic_csi_from_mask(mask_upright)
        csi_arch = _arch_from_csi(csi_dyn)

        icsi, info_i = compute_csi_intensity(rgb_tight, mask_tight, strong_tau=0.75, weak_tau=0.45, gamma=1.2)
        csi_bin, info_b = compute_csi_binary(mask_tight)

        _label0, _conf0, probs0 = classify_with_mask(pil_tight, mask_tight, mask_mode="mean")
        probs = _apply_soft_prior(probs0, csi_dyn)

        # ✅ Option B final decision (argmax)
        label = choose_arch_label(probs)
        conf = float(probs.get(label, 0.0))

        payload = dict(det)
        payload.update({
            "mask": encode_png_to_data_url(mask),
            "prediction": label,
            "confidence": conf,
            "probabilities": probs,
            "csi_intensity": icsi,
            "csi_binary": csi_bin,
            "csi_info": {"intensity": info_i, "binary": info_b},
            "overlay": overlay,
            "csi": float(csi_dyn),
            "csi_arch": csi_arch,
            "mask_overlay": encode_png_to_data_url(mask_tight),
        })
        out.append(payload)

    return {"status": "ok", "boxes": det_payload.get("boxes", []), "detections": out}