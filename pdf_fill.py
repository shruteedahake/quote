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




---- changes


def fill_pdf_form(template_bytes: bytes, field_map: dict) -> bytes:
    doc = fitz.open(stream=template_bytes, filetype="pdf")

    all_page_tokens = []
    for page in doc:
        all_page_tokens.extend(_collect_tokens(page.get_text("text")))
    all_page_tokens = list(dict.fromkeys(all_page_tokens))

    for page in doc:
        page_text = page.get_text("text")
        tokens = _collect_tokens(page_text)

        # Replace {{tokens}}
        for raw_token in tokens:
            value = field_map.get(raw_token)
            if value in (None, ""):
                continue

            token_variants = [f"{{{{{raw_token}}}}}", f"{{{raw_token}}}"]
            for tv in token_variants:
                _replace_token(page, tv, value)

        # Place next to labels
        for raw_token in tokens:
            value = field_map.get(raw_token)
            if value in (None, ""):
                continue

            label = f"{raw_token.strip()}:"
            _place_next_to_label(page, label, value)

    out = io.BytesIO()
    doc.save(out, deflate=True)
    doc.close()
    return out.getvalue()





-------------------
def fill_pdf_form(template_bytes: bytes, field_map: dict) -> bytes:
    doc = fitz.open(stream=template_bytes, filetype="pdf")

    all_page_tokens = []
    for page in doc:
        all_page_tokens.extend(_collect_tokens(page.get_text("text")))
    all_page_tokens = list(dict.fromkeys(all_page_tokens))

    for page in doc:
        page_text = page.get_text("text")
        print("PAGE TEXT:")
        print(page.get_text("text"))
        tokens = _collect_tokens(page_text)

        # Replace {{tokens}}
        for raw_token in tokens:
            value = field_map.get(raw_token)
            if value in (None, ""):
                continue

            token_variants = [f"{{{{{raw_token}}}}}", f"{{{raw_token}}}"]
            for tv in token_variants:
                _replace_token(page, tv, value)

        # Place next to labels
        for raw_token in tokens:
            value = field_map.get(raw_token)
            if value in (None, ""):
                continue

            label = f"{raw_token.strip()}:"
            _place_next_to_label(page, label, value)

    out = io.BytesIO()
    doc.save(out, deflate=True)
    doc.close()
    return out.getvalue()


--------- change 2
def fill_pdf_form(template_bytes: bytes, field_map: dict) -> bytes:
    doc = fitz.open(stream=template_bytes, filetype="pdf")

    for page in doc:
        page_text = page.get_text("text")
        print("PAGE TEXT:")
        print(page_text)

        for pdf_key, value in field_map.items():
            if value in (None, ""):
                continue

            # SubDoc.BrokerName -> Broker Name
            label_text = pdf_key.split(".")[-1]
            label_text = re.sub(r"([a-z])([A-Z])", r"\1 \2", label_text)

            placed = _place_next_to_label(page, f"{label_text}:", value)

            if not placed:
                _replace_token(page, pdf_key, value)

    out = io.BytesIO()
    doc.save(out, deflate=True)
    doc.close()
    return out.getvalue()


-0--------------------------
def build_pdf_field_map(abc_json: dict, gw_json: dict) -> dict:
    today = datetime.today()
    quote_date = today.strftime("%d/%m/%y")
    expiry_date = (today + timedelta(days=30)).strftime("%d/%m/%y")

    return {
        "SubDoc.BrokerName": safe_get(abc_json, "Broker Name"),
        "SubDoc.OragnizationName": safe_get(abc_json, "Oragnization Name"),
        "SubDoc.BrokerEmail": safe_get(abc_json, "Broker Email"),
        "SubDoc.NamedInsured": safe_get(abc_json, "Named Insured"),
        "SubDoc.NameandMailingAddress": safe_get(abc_json, "Name and Mailing Address"),

        "QuoteDate": quote_date,
        "QuoteExpiryDate": expiry_date,

        "TypeOfCover": "Commercial Property",
        "CoverageBasis": "Fire & Allied Perils",

        "SubDoc.EffectiveDate": safe_get(abc_json, "Effective Date"),
        "SubDoc.ExpirationDate": safe_get(abc_json, "Expiration Date"),
        "SubDoc.LimitofLiabilit": safe_get(abc_json, "Limit of Liability"),

        "TotalPayablePremium": f"$ {safe_get(gw_json, 'totalPremium.amount')}",
        "Taxes": f"$ {safe_get(gw_json, 'taxesandSurcharges.amount')}",
    }



----------- vhange 2

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



_______

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
