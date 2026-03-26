# backend/utils/recs.py
from __future__ import annotations
from typing import List, Dict, Any, Optional
from pathlib import Path
import json
import time

# --- Optional Firestore (overlay) ---
_HAS_FS = False
try:
    import firebase_admin
    from firebase_admin import credentials, firestore
    _HAS_FS = True
except Exception:
    _HAS_FS = False

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
JSON_CANDIDATES = ("product.ph.json", "products.ph.json")

# Tiny cache to avoid rereading on every request
_JSON_CACHE: Dict[str, Any] = {"items": [], "mtime": 0.0}
_FS_CACHE: Dict[str, Any] = {"items": [], "t": 0.0}  # 10s TTL


def _norm_arch(arch: str) -> str:
    s = (arch or "").strip().lower()
    if s == "flat":   return "Flat"
    if s == "normal": return "Normal"
    if s == "high":   return "High"
    return "Unknown"


def _load_json_products() -> List[Dict[str, Any]]:
    """Load baseline products from data/product*.json with simple mtime cache."""
    path = None
    for name in JSON_CANDIDATES:
        p = DATA / name
        if p.exists():
            path = p
            break
    if not path:
        return []

    mtime = path.stat().st_mtime
    if _JSON_CACHE["items"] and _JSON_CACHE["mtime"] == mtime:
        return _JSON_CACHE["items"]

    try:
        obj = json.loads(path.read_text(encoding="utf-8"))
        items = obj.get("items") if isinstance(obj, dict) else obj
        items = items if isinstance(items, list) else []
        # normalize product_id field
        for it in items:
            if "product_id" not in it and "id" in it:
                it["product_id"] = it["id"]
        _JSON_CACHE.update({"items": items, "mtime": mtime})
        return items
    except Exception:
        return []


def _fs_client():
    if not _HAS_FS:
        return None
    if not getattr(firebase_admin, "_apps", None):
        try:
            # prefer ADC (GOOGLE_APPLICATION_CREDENTIALS); if not set, init default
            cred = credentials.ApplicationDefault()
            firebase_admin.initialize_app(cred)
        except Exception:
            return None
    try:
        return firestore.client()
    except Exception:
        return None


def _fetch_firestore_products() -> List[Dict[str, Any]]:
    """Fetch products from Firestore with a short TTL cache (10s)."""
    now = time.time()
    if _FS_CACHE["items"] and (now - _FS_CACHE["t"] < 10.0):
        return _FS_CACHE["items"]

    fs = _fs_client()
    if fs is None:
        _FS_CACHE.update({"items": [], "t": now})
        return []

    items: List[Dict[str, Any]] = []
    try:
        for d in fs.collection("products").stream():
            obj = d.to_dict() or {}
            obj.setdefault("product_id", d.id)
            # coerce any comma-strings to lists
            for key in ("arch_claims", "country", "materials", "tags"):
                v = obj.get(key)
                if isinstance(v, str):
                    obj[key] = [x.strip() for x in v.split(",") if x.strip()]
            items.append(obj)
    except Exception:
        items = []
    _FS_CACHE.update({"items": items, "t": now})
    return items


def _merge_products(base: List[Dict[str, Any]], overlay: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Overlay Firestore products on top of JSON by product_id."""
    by_id: Dict[str, Dict[str, Any]] = {}
    for p in base:
        pid = str(p.get("product_id") or "")
        if not pid:
            continue
        by_id[pid] = dict(p)

    for p in overlay:
        pid = str(p.get("product_id") or "")
        if not pid:
            continue
        # overlay/insert
        if pid in by_id:
            by_id[pid].update(p)
        else:
            by_id[pid] = dict(p)

    # stable-ish order: keep JSON order first, then new Firestore-only items
    known = [pid for pid in [str(p.get("product_id") or "") for p in base] if pid]
    out = [by_id[pid] for pid in known if pid in by_id]
    # append any new ids
    for pid, obj in by_id.items():
        if pid not in known:
            out.append(obj)
    return out


def recommend_insoles(arch_type: str, *, country: str = "PH", user: Optional[dict] = None, k: int = 3) -> List[Dict[str, Any]]:
    """
    Hybrid source:
      1) Load JSON (baseline)
      2) If Firestore available, overlay changes/additions
    """
    arch = _norm_arch(arch_type)
    if arch == "Unknown":
        return []

    base = _load_json_products()
    fs_items = _fetch_firestore_products()
    products = _merge_products(base, fs_items)

    # Treat "Normal" as compatible with vendor label "Neutral"
    vendor_ok = {"Neutral"} if arch == "Normal" else set()

    scored: List[tuple[float, Dict[str, Any]]] = []
    for p in products:
        claims = set(map(str, (p.get("arch_claims") or [])))
        if not (arch in claims or (claims & vendor_ok)):
            continue

        score = 0.0
        # + country match
        if country and country in (p.get("country") or []):
            score += 2.0
        # brand nudge example
        brand = (p.get("brand") or "").lower()
        if "dr. kong" in brand or "dr kong" in brand:
            score += 0.5
        # budget nudge
        price = p.get("price")
        try:
            if price is not None and user and isinstance(user.get("budget"), (int, float)):
                if float(price) <= float(user["budget"]):
                    score += 0.3
        except Exception:
            pass

        scored.append((score, p))

    scored.sort(key=lambda t: t[0], reverse=True)
    top = [p for _, p in scored[: max(1, int(k))]]

    # normalize shape for your PDF/UI
    return [{
        "name": p.get("name") or "Insole",
        "url": p.get("url") or "",
        "note": p.get("note") or "",
        "price": p.get("price"),
        "currency": p.get("currency"),
        "tags": p.get("tags") or [],
    } for p in top]
