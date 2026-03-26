# app.py
from __future__ import annotations

import os
import logging
from typing import Optional

# -------------------------------------------------------------------
# Environment stability:
# Only force CPU on Windows (so Linux GPU servers can still use CUDA)
# -------------------------------------------------------------------
if os.name == "nt":
    os.environ.setdefault("CUDA_VISIBLE_DEVICES", "")
    os.environ.setdefault("ORT_DML_ENABLE_GPU_FALLBACK", "0")

from flask import Flask, request, jsonify, send_file
from flask_cors import CORS

from utils.config import HEALTH_SNAPSHOT
from utils.pipeline import detect_instances, classify_crop, process_end_to_end
from utils.report import (
    build_report_payload,
    generate_combined_pdf_from_payloads,
)

# Try to import the recommender. If missing, fall back to a small shim.
try:
    from utils.recs import recommend_insoles as _recommend_insoles  # type: ignore
except Exception:
    _recommend_insoles = None

def recommend_insoles(
    arch_type: str,
    *,
    country: str = "PH",
    user: Optional[dict] = None,
    k: int = 3
):
    """
    Wrapper that safely calls utils.recs.recommend_insoles() if present.
    Returns [] on any error.
    """
    if _recommend_insoles is None:
        return []
    try:
        return _recommend_insoles(arch_type, country=country, user=user, k=k)
    except Exception:
        return []

# Optional saved-images blueprint
try:
    from utils.saved import bp as save_images_bp
except Exception:
    save_images_bp = None

ARCH_CANON = {"flat": "Flat", "normal": "Normal", "high": "High"}

def _norm_arch(value: Optional[str]) -> str:
    if not value:
        return "Unknown"
    v = str(value).strip().lower()
    return ARCH_CANON.get(v, "Unknown")

def _json_error(message: str, code: int = 400, *, detail: Optional[str] = None):
    payload = {"status": "error", "error": message}
    if detail:
        payload["detail"] = detail
    return jsonify(payload), code

def create_app() -> Flask:
    app = Flask(__name__)

    # ---------------------------------------------------------------
    # CORS:
    # If you are NOT using cookies/session auth, supports_credentials=False
    # (Firebase client auth typically doesn't need cookies here)
    # ---------------------------------------------------------------
    CORS(
        app,
        resources={r"/*": {"origins": [
            "http://localhost:3000",
            "http://127.0.0.1:3000",
            # If you deploy a frontend domain, add it here:
            # "https://your-frontend-domain.com",
            "*"
        ]}},
        supports_credentials=False,
        expose_headers=["Content-Type", "Content-Disposition"],
    )

    app.logger.setLevel(logging.INFO)

    if save_images_bp is not None:
        app.register_blueprint(save_images_bp)

    # -------------------- Health --------------------
    @app.route("/health")
    def health():
        try:
            snap = HEALTH_SNAPSHOT()
            return jsonify({"status": "ok", "snapshot": snap})
        except Exception as e:
            app.logger.exception("Health snapshot failed")
            return _json_error("health failed", 500, detail=str(e))

    # -------------------- Inference --------------------
    @app.route("/detect", methods=["POST"])
    def detect():
        data = request.get_json(silent=True) or {}
        if "image" not in data:
            return _json_error("No image provided", 400)
        try:
            payload = detect_instances(data["image"])
            # Expected shape: {"status":"ok","boxes":[...],"detections":[...]}
            return jsonify(payload)
        except Exception as e:
            app.logger.exception("Detection failed")
            return _json_error("Detection failed", 500, detail=str(e))

    @app.route("/classify", methods=["POST"])
    def classify():
        data = request.get_json(silent=True) or {}
        if "image" not in data:
            return _json_error("No image provided", 400)
        try:
            result = classify_crop(data["image"], polygon=data.get("polygon"))
            return jsonify(result)
        except Exception as e:
            app.logger.exception("Classification failed")
            return _json_error("Classification failed", 500, detail=str(e))

    @app.route("/process", methods=["POST"])
    def process_route():
        data = request.get_json(silent=True) or {}
        if "image" not in data:
            return _json_error("No image provided", 400)
        try:
            payload = process_end_to_end(data["image"], save=bool(data.get("save", False)))
            return jsonify(payload)
        except Exception as e:
            app.logger.exception("Process failed")
            return _json_error("Process failed", 500, detail=str(e))

    # -------------------- Report JSON (for modal) --------------------
    @app.route("/report", methods=["POST"])
    def report_payload():
        data = request.get_json(silent=True) or {}
        image_name = data.get("image_name")
        arch_raw = data.get("arch_type")
        foot_side = data.get("foot_side")

        if not image_name:
            return _json_error("Missing image_name", 400)

        arch_type = _norm_arch(arch_raw)
        country = (data.get("country") or "PH").upper()
        user_ctx = {"activity": data.get("activity"), "budget": data.get("budget")}

        try:
            insoles = recommend_insoles(arch_type, country=country, user=user_ctx, k=3)
            if not insoles:
                insoles = None  # triggers report defaults

            payload = build_report_payload(
                image_name=image_name,
                arch_type=arch_type,
                foot_side=foot_side,
                csi=data.get("csi"),
                overlay=data.get("overlay"),
                insoles=insoles,
                # no image_uri here to keep response light
            )
            return jsonify(payload)
        except Exception as e:
            app.logger.exception("Report payload build failed")
            return _json_error("Report payload build failed", 500, detail=str(e))

    # -------------------- Combined (multi-page) PDF ONLY --------------------
    @app.route("/report/pdf/batch", methods=["POST"])
    def report_pdf_batch():
        body = request.get_json(silent=True) or {}
        items = body.get("items")
        if not isinstance(items, list) or not items:
            return _json_error("Missing or empty 'items' list", 400)

        try:
            payloads = []
            for it in items:
                image_name = it.get("image_name")
                arch_raw = it.get("arch_type")
                if not image_name or arch_raw is None:
                    return _json_error("Each item needs image_name and arch_type", 400)

                arch_type = _norm_arch(arch_raw)
                insoles = it.get("insoles") or None
                image_uri = it.get("image") or it.get("image_url")

                payloads.append(
                    build_report_payload(
                        image_name=image_name,
                        arch_type=arch_type,
                        foot_side=it.get("foot_side"),
                        csi=it.get("csi"),
                        overlay=it.get("overlay"),
                        insoles=insoles,
                        image_uri=image_uri,
                    )
                )

            pdf = generate_combined_pdf_from_payloads(payloads)
            return send_file(
                pdf,
                as_attachment=False,
                download_name="foot_arch_report.pdf",
                mimetype="application/pdf",
            )
        except Exception as e:
            app.logger.exception("Combined report generation failed")
            return _json_error("Combined report generation failed", 500, detail=str(e))

    return app

if __name__ == "__main__":
    app = create_app()
    app.run(host="0.0.0.0", port=5000, debug=True, threaded=True)
