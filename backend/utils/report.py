# backend/utils/report.py
"""
Report utilities for LOFU (exports build_report_payload + generate_combined_pdf_from_payloads).

- US Letter page
- Times New Roman (ReportLab Times) 12 pt, 1.5 line spacing (18 pt)
- Embedded image (data URL, http/https, or local path)
- Fixed header spacing (no overlap with title)
- Fixed blue section bar spacing
- No cover page

Non-dev copy overrides:
- Base defaults live in backend/utils/report_static.py
- Optional JSON overrides in backend/content/report_copy.json (EXPLANATIONS, CARE_TIPS, SHOE_TIPS)
- No default insoles: insoles must be supplied explicitly to build_report_payload()
"""

import io
import re
import base64
from urllib.request import urlopen
from datetime import datetime
from typing import Iterable, Optional, Dict, Any, List, Sequence

from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
from reportlab.lib.utils import ImageReader

# --------------------- Visual constants ---------------------
ACCENT = (0.10, 0.45, 0.86)
TEXT_PRIMARY = (0, 0, 0)
TEXT_SECONDARY = (0.2, 0.2, 0.2)
TEXT_MUTED = (0.35, 0.35, 0.35)
LINK_BLUE = (0.00, 0.00, 1.00)

PAGE_SIZE = letter
PAGE_MARGIN = 56
TITLE_SIZE = 16
H2_SIZE = 14
BODY_SIZE = 12
LEADING = 18  # 1.5 spacing

# Times family (built-in)
FONT_REG = "Times-Roman"
FONT_BOLD = "Times-Bold"
FONT_ITAL = "Times-Italic"
FONT_BI   = "Times-BoldItalic"

# --------------------- Static copy (defaults) ---------------------
from .report_static import EXPLANATIONS, CARE_TIPS, SHOE_TIPS

# --------------------- Non-dev copy overrides ---------------------
# Loads JSON from backend/content/report_copy.json if present
try:
    from .report_copy_loader import load_copy  # small helper that returns {} if file missing
    _copy = load_copy()
    if isinstance(_copy, dict):
        if isinstance(_copy.get("EXPLANATIONS"), dict):
            EXPLANATIONS.update(_copy["EXPLANATIONS"])
        if isinstance(_copy.get("CARE_TIPS"), dict):
            CARE_TIPS.update(_copy["CARE_TIPS"])
        if isinstance(_copy.get("SHOE_TIPS"), dict):
            SHOE_TIPS.update(_copy["SHOE_TIPS"])
except Exception:
    # Fail-safe: ignore copy loading errors and keep Python defaults
    pass

# --------------------- Helpers ---------------------
def _arch_label(arch_type: str) -> str:
    return {"Flat": "Flat Arch", "Normal": "Normal Arch", "High": "High Arch"}.get(arch_type, "Unknown")

def _norm_arch(arch_type: str) -> str:
    s = (arch_type or "").strip().lower()
    if s == "flat": return "Flat"
    if s == "normal": return "Normal"
    if s == "high": return "High"
    return "Unknown"

def _normalize_side(side: Optional[str]) -> Optional[str]:
    if not side: return None
    s = str(side).strip().lower()
    if s in ("left", "left foot", "l"):  return "Left"
    if s in ("right", "right foot", "r"): return "Right"
    return None

def _infer_side_from_name(image_name: Optional[str]) -> Optional[str]:
    if not image_name: return None
    m = re.search(r"_(\d+)(?:\.(?:png|jpg|jpeg|webp|bmp|tif|tiff))?$", image_name, re.IGNORECASE)
    if m:
        try:
            idx = int(m.group(1))
            if idx == 1: return "Left"
            if idx == 2: return "Right"
        except ValueError:
            pass
    s = (image_name or "").strip().lower()
    if "left" in s: return "Left"
    if "right" in s: return "Right"
    return None

def _display_image_name(image_name: Optional[str], foot_side: Optional[str]) -> str:
    side = _normalize_side(foot_side) or _infer_side_from_name(image_name)
    if side in ("Left", "Right"):
        return f"{side} Foot"
    return image_name or "Foot"

def _set_color(c, rgb):
    c.setFillColorRGB(*rgb)
    c.setStrokeColorRGB(*rgb)

def _draw_section_title(c, x, y, text, gap_before=12, bar_w=6, pad_left=6):
    """
    Section header with blue bar and built-in vertical padding to avoid overlap.
    """
    y -= gap_before
    bar_h = max(12, int(LEADING * 0.9))     # ~16 for 12/18
    bar_bottom = y - int(bar_h * 0.70)

    c.setFillColorRGB(*ACCENT)
    c.rect(x, bar_bottom, bar_w, bar_h, stroke=0, fill=1)

    _set_color(c, TEXT_PRIMARY)
    c.setFont(FONT_BOLD, H2_SIZE)
    c.drawString(x + bar_w + pad_left, y, text)

    return y - 10  # space after the title

def _draw_divider(c, x, y, w):
    c.setLineWidth(0.5)
    _set_color(c, (0.8, 0.84, 0.90))
    c.line(x, y, x + w, y)
    _set_color(c, TEXT_PRIMARY)
    return y - 10  # extra breathing room

def _draw_wrapped_text(c, x, y, text, max_width, font_name=FONT_REG, font_size=BODY_SIZE, leading=LEADING):
    if not text: return y
    c.setFont(font_name, font_size)
    _set_color(c, TEXT_SECONDARY)
    words = text.split()
    lines, line = [], []
    for w in words:
        probe = (" ".join(line) + (" " if line else "") + w) if line else w
        if c.stringWidth(probe, font_name, font_size) <= max_width:
            line.append(w)
        else:
            if line: lines.append(" ".join(line))
            line = [w]
    if line: lines.append(" ".join(line))
    t = c.beginText(x, y)
    t.setFont(font_name, font_size)
    t.setLeading(leading)
    for ln in lines:
        t.textLine(ln)
    c.drawText(t)
    _set_color(c, TEXT_PRIMARY)
    return y - leading * len(lines)

def _draw_bullet_list(c, x, y, items, max_width, bullet="•", font_name=FONT_REG, font_size=BODY_SIZE, leading=LEADING):
    indent = 14
    for it in items or []:
        text = it.get("text") if isinstance(it, dict) else str(it)
        if not text: continue
        c.setFont(font_name, font_size)
        _set_color(c, TEXT_PRIMARY)
        c.drawString(x, y, bullet)
        y = _draw_wrapped_text(c, x + indent, y, text, max_width - indent, font_name, font_size, leading) - 2
    return y

def _draw_clickable_text(c, x, y, text, url, font_name=FONT_BOLD, font_size=BODY_SIZE):
    if not text: return y
    c.setFont(font_name, font_size)
    c.setFillColorRGB(*LINK_BLUE)
    c.drawString(x, y, text)
    w = c.stringWidth(text, font_name, font_size)
    if url:
        c.linkURL(url, (x, y - 2, x + w, y + font_size), relative=0)
    _set_color(c, TEXT_PRIMARY)
    return y - (font_size + 3)

# ---------------- Image helpers ----------------
def _image_reader_from_any(src: str) -> Optional[ImageReader]:
    if not src or not isinstance(src, str): return None
    try:
        if src.startswith("data:image/"):
            _, b64 = src.split(",", 1)
            return ImageReader(io.BytesIO(base64.b64decode(b64)))
        if src.startswith("http://") or src.startswith("https://"):
            with urlopen(src) as resp:
                return ImageReader(io.BytesIO(resp.read()))
        return ImageReader(src)
    except Exception:
        return None

def _draw_image_block(c, x, y, max_w, max_h, img_reader: ImageReader):
    try:
        iw, ih = img_reader.getSize()
    except Exception:
        return y
    scale = min(max_w / iw, max_h / ih, 1.0)
    dw, dh = iw * scale, ih * scale
    img_y = y - dh
    c.setLineWidth(0.6)
    _set_color(c, (0.85, 0.90, 0.95))
    c.rect(x - 2, img_y - 2, dw + 4, dh + 4, stroke=1, fill=0)
    _set_color(c, TEXT_PRIMARY)
    c.drawImage(img_reader, x, img_y, width=dw, height=dh, mask='auto', preserveAspectRatio=True, anchor='nw')
    return img_y - 10

# ---------------- Builders (exported) ----------------
def build_report_payload(
    image_name: str,
    arch_type: str,
    *,
    foot_side: Optional[str] = None,
    explanations: Optional[Dict[str, str]] = None,
    insoles: Optional[Iterable[Dict[str, Any]]] = None,
    now: Optional[datetime] = None,
    csi: Optional[float] = None,
    overlay: Optional[Dict[str, float]] = None,
    image_uri: Optional[str] = None,  # data URL / http(s) / local path
) -> Dict[str, Any]:
    """
    Construct a structured payload for a single result page.
    Notes:
      - Non-dev copy overrides (JSON) are already merged into EXPLANATIONS/CARE_TIPS/SHOE_TIPS at import time.
      - No default insoles: pass `insoles=[{name,url,...}, ...]` to include a section; leave None/[] to hide it.
    """
    arch = _norm_arch(arch_type)
    exps = explanations or EXPLANATIONS
    expl_text = exps.get(arch, "No explanation available.")
    arch_label = _arch_label(arch)

    # No default insoles: only use what caller supplies
    insoles_list: List[Dict[str, Any]] = list(insoles) if insoles else []

    ts = (now or datetime.now()).strftime("%Y-%m-%d %H:%M:%S")
    display_name = _display_image_name(image_name, foot_side)

    payload: Dict[str, Any] = {
        "title": "Foot Arch Classification Report",
        "generated_on": ts,
        "image_name": display_name,
        "original_image_name": image_name,
        "arch_type": arch,
        "arch_label": arch_label,
        "explanation": expl_text,
        "care_tips": CARE_TIPS.get(arch, []),
        "shoe_tips": SHOE_TIPS.get(arch, []),
        "when_to_seek_help": [],
        "insoles": insoles_list,
        "disclaimer": (
            "This report provides general information and is not a medical diagnosis. "
            "If you experience pain, functional limitation, or other concerning symptoms, "
            "please consult a qualified healthcare professional."
        ),
    }

    if isinstance(overlay, dict):
        oy: Dict[str, float] = {}
        for key in ("fore_y", "arch_y1", "arch_y2"):
            val = overlay.get(key)
            if isinstance(val, (int, float)):
                oy[key] = float(val)
        if oy:
            payload["overlay"] = oy

    if isinstance(csi, (int, float)):
        payload["csi"] = float(csi)

    if image_uri:
        payload["image_uri"] = image_uri

    return payload

# ---------------- Header/Footer + page drawing ----------------
def _draw_header_footer(c, page_w, page_h, margin, title="Foot Arch Classification Report"):
    """
    Draw header HIGHER and start content LOWER so nothing overlaps.
    """
    rule_y = page_h - margin + 16  # moved up to avoid touching title
    _set_color(c, ACCENT)
    c.setLineWidth(1.2)
    c.line(margin, rule_y, page_w - margin, rule_y)

    _set_color(c, TEXT_PRIMARY)
    c.setFont(FONT_BOLD, 12)
    c.drawString(margin, rule_y + 4, "LOFU")
    c.setFont(FONT_REG, 12)
    c.drawRightString(page_w - margin, rule_y + 4, datetime.now().strftime("%Y-%m-%d %H:%M"))

    # Footer
    _set_color(c, (0.8, 0.84, 0.90))
    c.setLineWidth(0.8)
    c.line(margin, margin - 14, page_w - margin, margin - 14)
    _set_color(c, TEXT_MUTED)
    c.setFont(FONT_REG, 12)
    c.drawString(margin, margin - 28, title)
    c.drawRightString(page_w - margin, margin - 28, f"Page {c.getPageNumber()}")

def _draw_report_page(c, payload: Dict[str, Any]):
    width, height = PAGE_SIZE
    margin = PAGE_MARGIN
    content_w = width - margin * 2

    _draw_header_footer(c, width, height, margin, title=payload.get("title", "Report"))

    # Start content lower to avoid header rule
    y = height - margin - 28

    # Main title
    c.setFont(FONT_BOLD, TITLE_SIZE)
    _set_color(c, TEXT_PRIMARY)
    c.drawString(margin, y, payload.get("title", "Report"))
    y -= 10
    y = _draw_divider(c, margin, y, content_w)

    # Meta row
    c.setFont(FONT_REG, BODY_SIZE)
    _set_color(c, TEXT_MUTED)
    c.drawString(margin, y, f"Generated on: {payload.get('generated_on','')}")
    c.drawRightString(margin + content_w, y, f"Predicted: {payload.get('arch_label') or _arch_label(payload.get('arch_type','Unknown'))}")
    _set_color(c, TEXT_PRIMARY)
    y -= 16

    # Identity
    c.setFont(FONT_BOLD, 12)
    c.drawString(margin, y, f"Image: {payload.get('image_name','')}")
    y -= 18

    # CSI (optional)
    if "csi" in payload:
        c.setFont(FONT_REG, BODY_SIZE)
        _set_color(c, TEXT_SECONDARY)
        c.drawString(margin, y, f"Chippaux–Smirak Index (CSI): {payload['csi']:.3f}")
        _set_color(c, TEXT_PRIMARY)
        y -= 16

    # Optional embedded image (fits safely, never overlaps text)
    img_uri = payload.get("image_uri")
    if img_uri:
        reader = _image_reader_from_any(img_uri)
        if reader:
            remaining = max(0, y - (margin + 150))  # keep at least ~150pt for text that follows
            max_h = min(int((height - 2 * margin) * 0.35), remaining)
            if max_h > 0:
                y = _draw_image_block(c, margin, y, content_w, max_h, reader)

    # Sections
    y = _draw_section_title(c, margin, y, "What this means")
    y = _draw_wrapped_text(c, margin, y, payload.get("explanation", ""), content_w)

    care = payload.get("care_tips") or []
    if care:
        y = _draw_section_title(c, margin, y, "Care tips")
        y = _draw_bullet_list(c, margin, y, care, content_w)

    shoes = payload.get("shoe_tips") or []
    if shoes:
        y = _draw_section_title(c, margin, y, "Shoe guidance")
        y = _draw_bullet_list(c, margin, y, shoes, content_w)

    insoles = payload.get("insoles") or []
    if insoles:
        title = "Recommended insoles"
        payload_arch_label = payload.get("arch_label") or _arch_label(payload.get("arch_type", "Unknown"))
        if payload_arch_label and payload_arch_label != "Unknown":
            title += f" — for {payload_arch_label}"
        y = _draw_section_title(c, margin, y, title)

        for rec in insoles:
            name = rec.get("name", "Insole")
            price = rec.get("price")
            curr  = rec.get("currency")
            display = f"• {name}"
            if price is not None and curr:
                display += f" — {price} {curr}"
            y = _draw_clickable_text(c, margin, y, display, rec.get("url", ""))
            note = rec.get("note")
            if note:
                y = _draw_wrapped_text(c, margin + 14, y, note, content_w - 14)

    disclaimer = payload.get("disclaimer")
    if disclaimer:
        y = _draw_divider(c, margin, y, content_w)
        c.setFont(FONT_ITAL, BODY_SIZE)
        _set_color(c, TEXT_MUTED)
        _draw_wrapped_text(c, margin, y, disclaimer, content_w)
        _set_color(c, TEXT_PRIMARY)

# ---------------- Generator (exported) ----------------
def generate_combined_pdf_from_payloads(payloads: Sequence[Dict[str, Any]]):
    """
    Generate one PDF with all payloads (no cover page).
    """
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=PAGE_SIZE)
    for payload in payloads:
        p = dict(payload or {})
        p.setdefault("title", "Foot Arch Classification Report")
        _draw_report_page(c, p)
        c.showPage()
    c.save()
    buf.seek(0)
    return buf
