# utils/config.py
import os, json
import numpy as np

# --- Model paths ---
DETECTOR_PATH    = "model/best1.pt"
CLASSIFIER_PATH  = "model/resnet18_finetuned_fixed.pt"

_LABEL_CANDIDATES = [
    "model/labels.json",
    "model/classes.txt",
]

IMAGE_ROOT      = "Image"
CAPTURED_DIRv2  = os.path.join(IMAGE_ROOT, "Captured_image")
CROPPED_DIRv2   = os.path.join(IMAGE_ROOT, "cropped_image")
os.makedirs(IMAGE_ROOT, exist_ok=True)
os.makedirs(CAPTURED_DIRv2, exist_ok=True)
os.makedirs(CROPPED_DIRv2, exist_ok=True)

# UI/API class order (keep this for app display order)
ARCH_CLASSES = ["Flat", "Normal", "High"]

def _load_model_classes():
    """
    Model OUTPUT order from training.
    Priority:
      - labels.json (dict: {"0":"Flat","1":"High","2":"Normal"} or similar)
      - classes.txt (one per line)
      - fallback to ARCH_CLASSES
    """
    # JSON maps first
    for p in _LABEL_CANDIDATES:
        if p.endswith(".json") and os.path.exists(p):
            try:
                with open(p, "r", encoding="utf-8") as f:
                    d = json.load(f)
                if isinstance(d, dict) and d:
                    try:
                        items = sorted(((int(k), str(v).strip()) for k, v in d.items()), key=lambda t: t[0])
                    except Exception:
                        items = sorted(((k, str(v).strip()) for k, v in d.items()), key=lambda t: int(t[0]))
                    vals = [v for _, v in items]
                    if vals:
                        return vals
            except Exception:
                pass

    # Plain txt fallback
    for p in _LABEL_CANDIDATES:
        if p.endswith(".txt") and os.path.exists(p):
            try:
                with open(p, "r", encoding="utf-8") as f:
                    lines = [ln.strip() for ln in f if ln.strip()]
                if lines:
                    return lines
            except Exception:
                pass

    return ARCH_CLASSES[:]

# NOTE: may be overridden at runtime by the checkpoint bundle ("classes")
MODEL_CLASSES = _load_model_classes()

# ============================================================
# Preprocess to MATCH YOUR v4 TRAINING
# v4 tf_eval:
#   Resize((224,224)) -> ToTensor -> ImageNet normalize
# ============================================================
GRAYSCALE = False

# Square resize for v4
INPUT_SIZE = (224, 224)       # (W, H)
RESIZE_TO_EVAL = None         # not used for v4; kept for compatibility
RESIZE_MODE = "square"        # "square" or "shorter_side"

# ImageNet torch normalization (0..1)
IMAGENET_TORCH_MEAN = np.array([0.485, 0.456, 0.406], dtype=np.float32)
IMAGENET_TORCH_STD  = np.array([0.229, 0.224, 0.225], dtype=np.float32)

# For mask fill in 0..255 space
IMAGENET_RGB_MEAN   = np.array([123.68, 116.779, 103.939], dtype=np.float32)

DETECTOR_IMG_DEFAULT = 640

DETECTOR_CLASS_NAMES_OVERRIDE = {
    0: "left",
    1: "right",
    2: "unknown",
}

# ===================== CSI knobs =====================
CSI_TRIM_TOP_FRAC      = 0.05
CSI_TRIM_BOTTOM_FRAC   = 0.08

CSI_FOREFOOT_TOP_FRAC     = 0.00
CSI_FOREFOOT_HEIGHT_FRAC  = 0.30

CSI_ARCH_TOP_FRAC      = 0.25
CSI_ARCH_BOTTOM_FRAC   = 0.75

CSI_BAND_HALF_FRAC     = 0.03

CSI_MORPH_KERNEL       = 7
CSI_MORPH_CLOSE_ITERS  = 2

def HEALTH_SNAPSHOT():
    versions = {}
    try:
        import numpy as _np; versions["numpy"] = _np.__version__
    except Exception: pass
    try:
        import cv2; versions["opencv"] = cv2.__version__
    except Exception: pass
    try:
        import PIL; versions["pillow"] = PIL.__version__
    except Exception: pass
    try:
        import ultralytics as _ul; versions["ultralytics"] = _ul.__version__
    except Exception: pass
    try:
        import torch as _t; versions["torch"] = _t.__version__
    except Exception: pass
    try:
        import torchvision as _tv; versions["torchvision"] = _tv.__version__
    except Exception: pass

    return {
        "status": "ok",
        "detector_path": DETECTOR_PATH,
        "classifier_path": CLASSIFIER_PATH,
        "MODEL_CLASSES": MODEL_CLASSES,
        "API_CLASSES": ARCH_CLASSES,
        "preprocess": {
            "grayscale": GRAYSCALE,
            "resize_mode": RESIZE_MODE,
            "resize_to_eval": RESIZE_TO_EVAL,
            "input_size": INPUT_SIZE,
            "imagenet_mean": IMAGENET_TORCH_MEAN.tolist(),
            "imagenet_std": IMAGENET_TORCH_STD.tolist(),
        },
        "detector_img_default": DETECTOR_IMG_DEFAULT,
        "versions": versions,
        "csi": {
            "trim_top": CSI_TRIM_TOP_FRAC,
            "trim_bottom": CSI_TRIM_BOTTOM_FRAC,
            "forefoot_top": CSI_FOREFOOT_TOP_FRAC,
            "forefoot_height": CSI_FOREFOOT_HEIGHT_FRAC,
            "arch_top": CSI_ARCH_TOP_FRAC,
            "arch_bottom": CSI_ARCH_BOTTOM_FRAC,
            "band_half": CSI_BAND_HALF_FRAC,
            "morph_kernel": CSI_MORPH_KERNEL,
            "morph_close_iters": CSI_MORPH_CLOSE_ITERS,
        }
    }
