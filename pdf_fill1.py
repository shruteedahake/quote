import io
import re
import fitz  # PyMuPDF
from utils import normalize_key, fmt_thousands, is_numeric_like, first_non_empty

def _white_and_write(page, rect, text, fontsize=10, width_pad=220):
    pad = 1.5
    wrect = fitz.Rect(rect.x0 - pad, rect.y0 - pad, rect.x1 + width_pad, rect.y1 + pad)
    page.draw_rect(wrect, fill=(1, 1, 1), color=None, stroke_opacity=0, fill_opacity=1, overlay=True)
    page.insert_textbox(wrect, str(text), fontname="helv", fontsize=fontsize, color=(0, 0, 0), align=0)

def _replace_token(page, token_text, value):
    rects = page.search_for(token_text)
    if not rects:
        return False
    out_val = fmt_thousands(value) if is_numeric_like(value) else value
    for r in rects:
        _white_and_write(page, r, out_val)
    return True

def _place_next_to_label(page, label_text, value, line_offset=0, width=420):
    rects = page.search_for(label_text)
    if not rects:
        return False
    r = rects[0]
    dy = (r.y1 - r.y0 + 12) * line_offset
    target = fitz.Rect(r.x1 + 6, r.y0 + dy - 1.5, r.x1 + width, r.y1 + dy + 10)
    out_val = fmt_thousands(value) if is_numeric_like(value) else value
    _white_and_write(page, target, out_val, width_pad=width - (r.x1 - r.x0))
    return True

def _collect_tokens(page_text):
    tokens = re.findall(r"{{(.+?)}}", page_text)
    tokens += [m for m in re.findall(r"{([^}]+)}}", page_text) if "{{" not in m]
    uniq = []
    seen = set()
    for t in tokens:
        if t not in seen:
            uniq.append(t)
            seen.add(t)
    return uniq q

def normalize_lookup_key(key) -> str:
    if not isinstance(key, str):
        return ""

    key = key.strip()
    if not key:
        return ""

    # Remove known prefixes
    key = key.replace("SubDoc.", "").replace("GWResponse.", "")

    # Remove everything except letters and numbers
    key = re.sub(r"[^a-zA-Z0-9]", "", key)

    return key.lower()

def fill_pdf_form(template_bytes: bytes, field_map: dict) -> bytes:
    doc = fitz.open(stream=template_bytes, filetype="pdf")

    for page in doc:
        page_text = page.get_text("text")
        tokens = _collect_tokens(page_text)

        for raw_token in tokens:
            lookup_key = normalize_lookup_key(raw_token)
            value = field_map.get(lookup_key)

            if value in (None, ""):
                continue

            token_variants = [f"{{{{{raw_token}}}}}", f"{{{raw_token}}}"]
            for tv in token_variants:
                _replace_token(page, tv, value)

            label = f"{raw_token.strip()}:"
            _place_next_to_label(page, label, value)

    out = io.BytesIO()
    doc.save(out, deflate=True)
    doc.close()
    return out.getvalue()
