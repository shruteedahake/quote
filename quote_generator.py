import io
import json
import requests
from urllib.parse import urlparse
from datetime import datetime, timedelta
from config import AzureConf
from azure.storage.blob import BlobServiceClient, ContentSettings
from pdf_fill import fill_pdf_form
from config import Defaults

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

def build_pdf_field_map(abc_data: dict, gw_data: dict) -> dict:
    today = datetime.today()
    quote_date = today.strftime("%d/%m/%y")
    expiry_date = (today + timedelta(days=30)).strftime("%d/%m/%y")

    return {
        # -------- Broker / Insured (ABC) --------
        "SubDoc.BrokerName": safe_get(abc_data, "brokername"),
        "oragnizationname": safe_get(abc_data, "oragnizationname"),
        "brokeremail": safe_get(abc_data, "brokeremail"),
        "namedinsured": safe_get(abc_data, "namedinsured"),
        "nameandmailingaddress": safe_get(abc_data, "nameandmailingaddress"),

        # -------- Dates --------------------------
        "quotedate": quote_date,
        "quoteexpirydate": expiry_date,

        # -------- Stubbed ------------------------
        ": Commercial Property ": "Commercial Property",
        "coveragebasis": "Fire & Allied Perils",

        # -------- Coverage Summary (ABC) ---------
        "effectivedate": safe_get(abc_data, "effectivedate"),
        "expirationdate": safe_get(abc_data, "expirationdate"),
        "limitofliabilit": safe_get(abc_data, "limitofliabilit"),

        # -------- Premium Summary (GW) ----------
        "totalpayablepremium": f"$ {safe_get(gw_data, 'totalpremiumamount')}",
        "taxes": f"$ {safe_get(gw_data, 'taxesandsurchargesamount')}",
    }


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

def generate_quote():
    try:
        # Download JSONs
        data_extraction_bytes = _download_bytes(Defaults.DATA_EXTRACTION_URL)
        gw_bytes = _download_bytes(Defaults.GW_URL)

        abc_json = flatten_json(json.loads(data_extraction_bytes.decode("utf-8")))
        gw_json = flatten_json(json.loads(gw_bytes.decode("utf-8")))

        # Download PDF template
        template_bytes = _download_bytes(Defaults.PDF_TEMPLATE_URL)

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
