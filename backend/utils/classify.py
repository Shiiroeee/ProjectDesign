# utils/classify.py
from __future__ import annotations

import warnings
from typing import Dict, Tuple, Optional

import numpy as np
import torch
import torchvision.transforms.functional as TF
from PIL import Image

from . import config as _cfg
from .io_utils import apply_mask_rgb, resize_for_model

_DEVICE = torch.device("cuda" if torch.cuda.is_available() else "cpu")
_MODEL: Optional[torch.nn.Module] = None
_IS_TS: bool = False
_LOGGED_INFO = False


def _strip_module_prefix(state: Dict[str, torch.Tensor]) -> Dict[str, torch.Tensor]:
    """If weights were saved from DataParallel, remove 'module.' prefix."""
    if not state:
        return state
    first = next(iter(state))
    if isinstance(first, str) and first.startswith("module."):
        return {k.replace("module.", "", 1): v for k, v in state.items()}
    return state


def _build_resnet18(num_classes: int) -> torch.nn.Module:
    """
    Build the SAME architecture you trained:
      model = torchvision.models.resnet18(weights=IMAGENET...) then replace fc
    For loading state_dict, weights should be None here.
    """
    import torchvision.models as models

    m = models.resnet18(weights=None)  # architecture matches torchvision ResNet18
    m.fc = torch.nn.Linear(m.fc.in_features, num_classes)
    return m


def _preprocess_rgb_255(arr_rgb_255: np.ndarray) -> torch.Tensor:
    """
    Input: HxWx3 in 0..255 (float32 or uint8)
    Output: 1x3xHxW float32 normalized with ImageNet mean/std
    """
    if not isinstance(arr_rgb_255, np.ndarray) or arr_rgb_255.ndim != 3 or arr_rgb_255.shape[2] != 3:
        raise ValueError(f"Expected HxWx3 ndarray, got {type(arr_rgb_255)} shape={getattr(arr_rgb_255,'shape',None)}")

    # Ensure range and dtype are sane
    x_np = np.clip(arr_rgb_255, 0, 255).astype(np.float32)

    # HWC -> CHW, scale to 0..1
    x = torch.from_numpy(x_np).permute(2, 0, 1) / 255.0

    # Normalize (ImageNet)
    x = TF.normalize(
        x,
        mean=_cfg.IMAGENET_TORCH_MEAN.tolist(),
        std=_cfg.IMAGENET_TORCH_STD.tolist(),
    )
    return x.unsqueeze(0)


def _map_model_probs_to_api(probs_model: np.ndarray) -> np.ndarray:
    """
    Map model output order (MODEL_CLASSES) -> API order (ARCH_CLASSES) by name.
    Example:
      bundle classes: ["Flat","High","Normal"]
      API classes:    ["Flat","Normal","High"]
    """
    norm = lambda s: str(s).strip().lower()
    idx = {norm(c): i for i, c in enumerate(_cfg.MODEL_CLASSES)}

    P_api = np.zeros((len(_cfg.ARCH_CLASSES),), dtype=np.float32)
    for i, name in enumerate(_cfg.ARCH_CLASSES):
        j = idx.get(norm(name))
        if j is not None and 0 <= j < probs_model.shape[0]:
            P_api[i] = float(probs_model[j])

    s = float(P_api.sum())
    if s > 0:
        P_api /= s
    return P_api


def _load_classifier() -> torch.nn.Module:
    """
    Load classifier model with robustness to common fc-head naming differences.

    Attempts (in order):
      1) TorchScript quick-path (if file ends with .ts/.ptc/.jit)
      2) Load checkpoint dict/module and strict load into a resnet18 with Linear head
      3) If strict load fails and checkpoint contains fc.1.* keys, attempt to recreate
         a Sequential head (Dropout + Linear) and load
      4) If still failing and checkpoint contains fc.<n>.* keys, attempt to remap
         keys 'fc.<n>.<name>' -> 'fc.<name>' and load
      5) If all fail, raise an informative RuntimeError.
    """
    global _MODEL, _IS_TS, _LOGGED_INFO
    if _MODEL is not None:
        return _MODEL

    path = _cfg.CLASSIFIER_PATH

    # 1) TorchScript quick-path (optional)
    try:
        if str(path).endswith((".ts", ".ptc", ".jit")):
            model = torch.jit.load(path, map_location=_DEVICE)
            model.eval().to(_DEVICE)
            _MODEL = model
            _IS_TS = True
            if not _LOGGED_INFO:
                print(f"[classifier] Loaded TorchScript from {path}")
                print(f"[classifier] MODEL_CLASSES={_cfg.MODEL_CLASSES} | ARCH_CLASSES={_cfg.ARCH_CLASSES}")
                _LOGGED_INFO = True
            return _MODEL
    except Exception:
        pass

    # 2) Bundle / checkpoint load
    try:
        ckpt = torch.load(path, map_location="cpu")
    except Exception as e:
        raise RuntimeError(f"Failed to torch.load classifier at '{path}': {e}") from e

    # Bundle stores "classes": [...]
    if isinstance(ckpt, dict):
        classes = ckpt.get("classes", None)
        if isinstance(classes, (list, tuple)) and len(classes) > 0:
            # override MODEL_CLASSES to match training output order
            _cfg.MODEL_CLASSES[:] = [str(v).strip() for v in classes]

    # Full module saved via torch.save(model)
    if isinstance(ckpt, torch.nn.Module):
        ckpt.eval().to(_DEVICE)
        _MODEL = ckpt
        _IS_TS = False
        if not _LOGGED_INFO:
            print(f"[classifier] Loaded full Module from {path}")
            print(f"[classifier] MODEL_CLASSES={_cfg.MODEL_CLASSES} | ARCH_CLASSES={_cfg.ARCH_CLASSES}")
            _LOGGED_INFO = True
        return _MODEL

    # Extract state dict
    if isinstance(ckpt, dict) and isinstance(ckpt.get("state_dict"), dict):
        state = ckpt["state_dict"]
    elif isinstance(ckpt, dict) and isinstance(ckpt.get("model"), dict):
        state = ckpt["model"]
    elif isinstance(ckpt, dict):
        # sometimes the dict itself is the state dict
        state = ckpt
    else:
        raise RuntimeError("Unsupported checkpoint format (expected dict/module).")

    state = _strip_module_prefix(state)

    # Build default resnet18 with a simple Linear head
    model = _build_resnet18(num_classes=len(_cfg.MODEL_CLASSES))

    # Attempt 1: strict load (preferred)
    try:
        model.load_state_dict(state, strict=True)
    except Exception as e_strict:
        # We'll attempt a few common fixes: recreate Sequential head, or remap fc.1 -> fc
        import re
        from collections import OrderedDict

        keys = list(state.keys())
        has_fc1 = any(k.startswith("fc.1.") for k in keys)
        has_fc_digit = any(re.match(r"^fc\.\d+\.", k) for k in keys)

        # Attempt 2: if checkpoint used Sequential head (e.g., fc = Sequential(Dropout, Linear))
        if has_fc1:
            try:
                in_features = model.fc.in_features
                model.fc = torch.nn.Sequential(
                    torch.nn.Dropout(p=0.5),
                    torch.nn.Linear(in_features, len(_cfg.MODEL_CLASSES)),
                )
                model.load_state_dict(state, strict=True)
            except Exception:
                # if it fails, we'll try renaming keys
                pass
            else:
                model.eval().to(_DEVICE)
                _MODEL = model
                _IS_TS = False
                if not _LOGGED_INFO:
                    print(f"[classifier] Loaded ResNet18 state_dict from {path} (recreated Sequential fc head).")
                    print(f"[classifier] MODEL_CLASSES={_cfg.MODEL_CLASSES} | ARCH_CLASSES={_cfg.ARCH_CLASSES}")
                    _LOGGED_INFO = True
                return _MODEL

        # Attempt 3: remap keys 'fc.<n>.*' -> 'fc.*' (safe quick fix)
        if has_fc_digit:
            try:
                new_state = OrderedDict()
                for k, v in state.items():
                    if k.startswith("fc."):
                        m = re.match(r"^fc\.(\d+)\.(.+)$", k)
                        if m:
                            newk = f"fc.{m.group(2)}"
                        else:
                            newk = k
                    else:
                        newk = k
                    new_state[newk] = v

                model = _build_resnet18(num_classes=len(_cfg.MODEL_CLASSES))
                model.load_state_dict(new_state, strict=True)
                model.eval().to(_DEVICE)
                _MODEL = model
                _IS_TS = False
                if not _LOGGED_INFO:
                    print(f"[classifier] Loaded ResNet18 state_dict from {path} (renamed fc.<n> -> fc).")
                    print(f"[classifier] MODEL_CLASSES={_cfg.MODEL_CLASSES} | ARCH_CLASSES={_cfg.ARCH_CLASSES}")
                    _LOGGED_INFO = True
                return _MODEL
            except Exception:
                # if rename fails, fall through to final error
                pass

        # Nothing worked — raise an informative error
        msg = (
            f"Classifier weights do not match torchvision ResNet18 architecture.\n"
            f"Path: {path}\n"
            f"This usually means CLASSIFIER_PATH points to the WRONG model file "
            f"(e.g., a ResNet variant with different conv1/fc shapes) OR the saved model used a different fc structure.\n"
            f"Attempted fixes: (1) strict load, (2) recreate Sequential fc if 'fc.1.*' keys detected, (3) rename 'fc.<n>.*' -> 'fc.*'.\n"
            f"Original strict-load error: {e_strict}"
        )
        raise RuntimeError(msg) from e_strict

    # If we reached here, strict load succeeded first try
    model.eval().to(_DEVICE)
    _MODEL = model
    _IS_TS = False

    if not _LOGGED_INFO:
        print(f"[classifier] Loaded ResNet18 state_dict from {path}")
        print(f"[classifier] MODEL_CLASSES={_cfg.MODEL_CLASSES} | ARCH_CLASSES={_cfg.ARCH_CLASSES}")
        _LOGGED_INFO = True

    return _MODEL


def classify_with_mask(
    pil_img: Image.Image,
    mask_np: Optional[np.ndarray] = None,
    mask_mode: str = "mul",  # "mul" or "mean" or "none"
) -> Tuple[str, float, Dict[str, float]]:
    """
    Returns: (label, confidence, prob_dist_in_API_order)
    prob_dist keys are ARCH_CLASSES: ["Flat","Normal","High"]
    """

    # 1) Resize/crop to match training EVAL (your io_utils does grayscale->resize->center crop)
    arr = resize_for_model(pil_img)  # HxWx3 float32 in 0..255
    if not isinstance(arr, np.ndarray) or arr.ndim != 3 or arr.shape[2] != 3:
        raise ValueError(f"resize_for_model must return HxWx3 array, got shape={getattr(arr, 'shape', None)}")

    H, W, _ = arr.shape

    # 2) Apply mask in the same (0..255) space
    if mask_np is not None:
        import cv2

        m = mask_np
        if m.ndim == 3:
            m = m[..., 0]
        m = cv2.resize(m.astype(np.uint8), (W, H), interpolation=cv2.INTER_NEAREST)
    else:
        m = None

    arr = apply_mask_rgb(arr, m, mode=mask_mode)

    # 3) Normalize to tensor
    x = _preprocess_rgb_255(arr).to(_DEVICE)

    # 4) Forward
    model = _load_classifier()
    with torch.inference_mode():
        out = model(x)
        if isinstance(out, (list, tuple)):
            out = out[0]
        logits = out.squeeze(0).to(torch.float32).cpu()
        probs_model = torch.softmax(logits, dim=-1).numpy()

    # 5) Map model probs -> API order
    P_api = _map_model_probs_to_api(probs_model)
    top = int(np.argmax(P_api))
    label = _cfg.ARCH_CLASSES[top]
    conf = float(P_api[top])
    dist = {_cfg.ARCH_CLASSES[i]: float(P_api[i]) for i in range(len(_cfg.ARCH_CLASSES))}
    return label, conf, dist