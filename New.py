import io
import json
import requests
from urllib.parse import urlparse
from datetime import datetime, timedelta

from azure.storage.blob import BlobServiceClient, ContentSettings


# -------------------------
# Azure / HTTP Download
# -------------------------

def _is_azure_blob_url(url: str) -> bool:
    try:
        host = urlparse(url).netloc.lower()
        return ".blob.core.windows.net" in host
    except Exception:
        return False


def _download_via_azure(url: str) -> bytes:
    parsed = urlparse(url)
    path = parsed.path.lstrip("/")
    if "/" not in path:
        raise ValueError(f"Invalid blob URL path: {path}")

    container, blob_path = path.split("/", 1)

    bsc = BlobServiceClient.from_connection_string(AzureConf.CONNECTION_STRING)
    blob_client = bsc.get_container_client(container).get_blob_client(blob_path)
    return blob_client.download_blob().readall()


def _download_bytes(url: str) -> bytes:
    if _is_azure_blob_url(url) and AzureConf.CONNECTION_STRING:
        try:
            return _download_via_azure(url)
        except Exception:
            pass

    resp = requests.get(url, timeout=60)
    resp.raise_for_status()
    return resp.content


# -------------------------
# JSON Helpers
# -------------------------

def flatten_json(data, parent_key="", sep="."):
    items = {}
    if isinstance(data, dict):
        for k, v in data.items():
            new_key = f"{parent_key}{sep}{k}" if parent_key else k
            items.update(flatten_json(v, new_key, sep))
    elif isinstance(data, list):
        for i, v in enumerate(data):
            new_key = f"{parent_key}{sep}{i}"
            items.update(flatten_json(v, new_key, sep))
    else:
        items[parent_key] = data
    return items


def safe_get(flat_json: dict, key: str) -> str:
    val = flat_json.get(key)
    return "" if val in (None, "null") else str(val)


# -------------------------
# PDF Field Mapping
# -------------------------

def build_pdf_field_map(abc_json: dict, gw_json: dict) -> dict:
    today = datetime.today()
    quote_date = today.strftime("%d/%m/%y")
    expiry_date = (today + timedelta(days=30)).strftime("%d/%m/%y")

    return {
        # -------------------------
        # 1. Broker & Client Details (ABC)
        # -------------------------
        "SubDoc.BrokerName": safe_get(abc_json, "SubDoc.BrokerName"),
        "SubDoc.OragnizationName": safe_get(abc_json, "SubDoc.OragnizationName"),
        "SubDoc.BrokerEmail": safe_get(abc_json, "SubDoc.BrokerEmail"),
        "SubDoc.NamedInsured": safe_get(abc_json, "SubDoc.NamedInsured"),
        "SubDoc.NameandMailingAddress": safe_get(abc_json, "SubDoc.NameandMailingAddress"),

        "QuoteDate": quote_date,
        "QuoteExpiryDate": expiry_date,

        # -------------------------
        # 2. Coverage Summary
        # -------------------------
        "TypeOfCover": "Commercial Property",
        "CoverageBasis": "Fire & Allied Perils",

        "SubDoc.EffectiveDate": safe_get(abc_json, "SubDoc.EffectiveDate"),
        "SubDoc.ExpirationDate": safe_get(abc_json, "SubDoc.ExpirationDate"),
        "SubDoc.LimitofLiabilit": safe_get(abc_json, "SubDoc.LimitofLiabilit"),

        # -------------------------
        # 3. Premium Summary (GW)
        # -------------------------
        "TotalPayablePremium": f"$ {safe_get(gw_json, 'GWResponse.totalPremium.amount')}",
        "Taxes": f"$ {safe_get(gw_json, 'GWResponse.taxesandSurcharges.amount')}",
    }


# -------------------------
# PDF Upload
# -------------------------

def _upload_pdf(filename: str, pdf_bytes: bytes) -> str:
    if not (AzureConf.CONNECTION_STRING and AzureConf.ACCOUNT_URL):
        raise RuntimeError("Missing Azure storage configuration")

    container_name = "quotes-output"

    bsc = BlobServiceClient.from_connection_string(AzureConf.CONNECTION_STRING)
    container_client = bsc.get_container_client(container_name)

    try:
        container_client.create_container()
    except Exception:
        pass

    blob_client = container_client.get_blob_client(filename)
    blob_client.upload_blob(
        io.BytesIO(pdf_bytes),
        overwrite=True,
        content_settings=ContentSettings(content_type="application/pdf"),
    )

    return f"{AzureConf.ACCOUNT_URL}/{container_name}/{filename}"


# -------------------------
# Main Entry Point
# -------------------------

def generate_quote(
    abc_json_blob_url: str,
    gw_json_blob_url: str,
    pdf_template_url: str,
):
    try:
        # Download JSONs
        abc_bytes = _download_bytes(abc_json_blob_url)
        gw_bytes = _download_bytes(gw_json_blob_url)

        abc_json = flatten_json(json.loads(abc_bytes.decode("utf-8")))
        gw_json = flatten_json(json.loads(gw_bytes.decode("utf-8")))

        # Download PDF template
        template_bytes = _download_bytes(pdf_template_url)

        # Build PDF field map
        pdf_field_map = build_pdf_field_map(abc_json, gw_json)

        # Fill PDF
        filled_pdf = fill_pdf_form(template_bytes, pdf_field_map)

        # Filename
        filename = f"{datetime.today().strftime('%d%m%y')}_Quote.pdf"

        # Upload
        blob_url = _upload_pdf(filename, filled_pdf)

        return {"error": False, "url": blob_url}

    except Exception as e:
        return {"error": True, "error_message": str(e)}
