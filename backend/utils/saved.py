# utils/saved.py
import os, base64, uuid
from pathlib import Path
from flask import Blueprint, request, jsonify
from .config import CAPTURED_DIRv2, CROPPED_DIRv2

bp = Blueprint("saved", __name__)

def _save_data_url(dir_path: str, data_url: str, prefix: str):
    if "," in data_url:
        data_url = data_url.split(",", 1)[1]
    b = base64.b64decode(data_url)
    Path(dir_path).mkdir(parents=True, exist_ok=True)
    name = f"{prefix}_{uuid.uuid4().hex[:8]}.png"
    out = str(Path(dir_path) / name)
    with open(out, "wb") as f:
        f.write(b)
    return out

def _handler():
    data = request.get_json(silent=True) or {}
    session = str(data.get("session", uuid.uuid4().hex[:6]))
    out = {"session": session, "files": {}, "urls": {}}

    cap = data.get("captured_image")
    if cap:
        fp = _save_data_url(CAPTURED_DIRv2, cap, f"{session}_capture")
        out["files"]["captured"] = fp

    crops = data.get("cropped_images") or []
    sides = data.get("sides") or [None] * len(crops)
    crop_files = []
    for i, durl in enumerate(crops):
        side = sides[i] or f"{i+1}"
        fp = _save_data_url(CROPPED_DIRv2, durl, f"{session}_{side}")
        crop_files.append(fp)
    if crop_files:
        out["files"]["crops"] = crop_files

    return jsonify(out)

@bp.route("/save-images", methods=["POST"])
def save_images_hyphen():
    return _handler()

@bp.route("/save_images", methods=["POST"])
def save_images_underscore():
    return _handler()
