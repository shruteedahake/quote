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
            # Fallback to HTTP/S for public or SAS URLs
            resp = requests.get(url, timeout=60)
            resp.raise_for_status()
            return resp.content
    resp = requests.get(url, timeout=60)
    resp.raise_for_status()
    return resp.content

def _read_excel_to_dict_url(url: str) -> dict:
    content = _download_bytes(url)
    df = pd.read_excel(io.BytesIO(content), engine="openpyxl")
    out = {}
    cols = [str(c).strip() for c in df.columns]
    if "Field" in cols and "Value" in cols:
        for _, row in df.iterrows():
            key = str(row["Field"]).strip()
            val = None if pd.isna(row["Value"]) else str(row["Value"]).strip()
            if key:
                out[normalize_key(key)] = val
    else:
        if df.shape[1] >= 2:
            for _, row in df.iterrows():
                key = str(row.iloc[0]).strip()
                val = None if pd.isna(row.iloc[1]) else str(row.iloc[1]).strip()
                if key:
                    out[normalize_key(key)] = val
    return out

def _compose_filename(extracted_map: dict, meta_map: dict, stubbed_map: dict) -> str:
    def prefer_key(*names):
        for n in names:
            v = first_non_empty(extracted_map.get(normalize_key(n)),
                                meta_map.get(normalize_key(n)),
                                stubbed_map.get(normalize_key(n)))
            if v:
                return v
        return ""
    ref_id = prefer_key("Agency Customer ID", "Reference Id", "ReferenceID")
    insured = prefer_key("Named Insured", "Owner Name", "Insured Name")
    broker = prefer_key("Broker / Agent Name", "Producer's Name Please Print", "Broker Name")
    date_val = prefer_key("Date", "Authorization Date", "Quote Date")
    date_fmt = mmddyyyy(pretty_date(date_val) or date_val)
    base = f"{date_fmt}_Quote.pdf"
    return base.strip("_")

def _upload_pdf(filename: str, pdf_bytes: bytes) -> str:
    """
    Upload the generated PDF into the 'quotes-output' container
    within the storage account specified by AZURE_STORAGE_CONNECTION_STRING.
    """
    if not (AzureConf.CONNECTION_STRING and AzureConf.ACCOUNT_URL):
        raise RuntimeError("Missing Azure storage configuration: AZURE_STORAGE_CONNECTION_STRING and AZURE_STORAGE_ACCOUNT_URL")

    container_name = "quotes-output"  # fixed target container per your requirement

    bsc = BlobServiceClient.from_connection_string(AzureConf.CONNECTION_STRING)
    container_client = bsc.get_container_client(container_name)
    try:
        container_client.create_container()
    except Exception:
        # Container may already exist or permission may already be set; safe to proceed
        pass

    blob_client = container_client.get_blob_client(filename)
    blob_client.upload_blob(
        io.BytesIO(pdf_bytes),
        overwrite=True,
        content_settings=ContentSettings(content_type="application/pdf"),
    )
    return f"{AzureConf.ACCOUNT_URL}/{container_name}/{filename}"

def generate_quote(extracted_json_url: str, meta_excel_url: str, stubbed_excel_url: str, pdf_template_url: str):
    try:
        extracted_bytes = _download_bytes(extracted_json_url)
        extracted_json = json.loads(extracted_bytes.decode("utf-8"))
        template_bytes = _download_bytes(pdf_template_url)

        extracted_map = flatten_json(extracted_json)
        meta_map = _read_excel_to_dict_url(meta_excel_url)
        stubbed_map = _read_excel_to_dict_url(stubbed_excel_url)

        filled_pdf = fill_pdf_form(template_bytes, extracted_map, meta_map, stubbed_map)

        filename = _compose_filename(extracted_map, meta_map, stubbed_map)
        blob_url = _upload_pdf(filename, filled_pdf)
        return {"error": False, "url": blob_url}
    except Exception as e:
        return {"error": True, "error_message": str(e)}



the above code is framed for generating the quote using the excel but now i want to generate a quote using the data direclty from the json file stored in azure blob. Please make the changes in the according to the new requirement.
Also i want to change the mapping of the pdf fields, the new mapping is as below: -
1.Broker & Client Details:
Broker Name: SubDoc.BrokerName The values from the input url should be fetched and fill in the place of"SubDoc.BrokerName"( (Should be fetched from the 2 input blob url)
Broker Company: SubDoc.OragnizationName The values from the input url should be fetched and fill in the place of "SubDoc.OragnizationName"(Should be fetched from the 2 input blob url)
Broker Email: SubDoc.BrokerEmail  The values from the input url should be fetched and fill in the place of"SubDoc.BrokerEmail"  (Should be fetched from the 2 input blob url) 
Insured Name: SubDoc.NamedInsured  The values from the input url should be fetched and fill in the place of"SubDoc.NamedInsured"  (Should be fetched from the 2 input blob url)
Risk Location Address: SubDoc.NameandMailingAddress The values from the input url should be fetched and fill in the place of" SubDoc.NameandMailingAddress"  (Should be fetched from the 2 input blob url) 
Quote Date: current date dd/mm/yy (Should have the logic on the code itself)
Quote Expiry Date: current date + 30days (Should have the logic on the code itself)

Accordingly make changes in the code and give me the complete new code.
