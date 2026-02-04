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
    return uniq

def _prefer_value(field_name, extracted_map, meta_map, stubbed_map):
    nk = normalize_key(field_name)
    v_ex = extracted_map.get(nk)
    v_meta = meta_map.get(nk)
    v_stub = stubbed_map.get(nk)
    return first_non_empty(v_ex, v_meta, v_stub)

def fill_pdf_form(template_bytes: bytes, extracted_map: dict, meta_map: dict, stubbed_map: dict) -> bytes:
    doc = fitz.open(stream=template_bytes, filetype="pdf")

    all_page_tokens = []
    for page in doc:
        all_page_tokens.extend(_collect_tokens(page.get_text("text")))
    all_page_tokens = list(dict.fromkeys(all_page_tokens))

    data_keys = set(list(meta_map.keys()) + list(stubbed_map.keys()) + list(extracted_map.keys()))
    fallback_label_candidates = [k for k in data_keys if k and k not in [normalize_key(t) for t in all_page_tokens]]

    for page in doc:
        page_text = page.get_text("text")
        tokens = _collect_tokens(page_text)
        for raw_token in tokens:
            token_variants = [f"{{{{{raw_token}}}}}", f"{{{raw_token}}}"]
            value = _prefer_value(raw_token, extracted_map, meta_map, stubbed_map)
            if value is None:
                continue
            for tv in token_variants:
                _replace_token(page, tv, value)

        for raw_token in tokens:
            if _prefer_value(raw_token, extracted_map, meta_map, stubbed_map) is None:
                continue
            label = f"{raw_token.strip()}:"
            _place_next_to_label(page, label, _prefer_value(raw_token, extracted_map, meta_map, stubbed_map))

        for nk in fallback_label_candidates:
            words = nk.split()
            if not words:
                continue
            label = f"{' '.join(w.capitalize() for w in words)}:"
            val = first_non_empty(extracted_map.get(nk), meta_map.get(nk), stubbed_map.get(nk))
            if val:
                _place_next_to_label(page, label, val)

    out = io.BytesIO()
    doc.save(out, deflate=True)
    doc.close()
    return out.getvalue()
