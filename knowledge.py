from crawler import crawl_website
from database import store_vector
from guardrails import allowed_domains_label, is_allowed_url, setting
from service_catalog import service_urls


def _chunk_text(text, max_chars=3500):

    clean = " ".join((text or "").split())
    if not clean:
        return []

    chunks = []
    start = 0
    while start < len(clean):
        chunk = clean[start:start + max_chars].strip()
        if chunk:
            chunks.append(chunk)
        start += max_chars

    return chunks


def add_knowledge(input_data, cloud_consent=False, human_reviewed=False):

    if not cloud_consent:
        return "Knowledge was not stored because DPDP cloud storage/embedding consent was not granted."

    if not human_reviewed:
        return "Knowledge was not stored because human review approval was not granted."

    if input_data.startswith("http"):
        if not is_allowed_url(input_data):
            return f"Blocked by CSC guardrail. Only these domains are allowed: {allowed_domains_label()}."

        pages = crawl_website(input_data)
        if not pages:
            return f"No allowed CSC pages were found. Allowed domains: {allowed_domains_label()}."

        stored = 0
        failed = 0

        for page in pages:
            ok, _ = store_vector(page["content"], source=page["url"], human_reviewed=human_reviewed)
            if ok:
                stored += 1
            else:
                failed += 1

        return f"{stored} pages added from website. {failed} pages failed."

    return "Manual pasted knowledge is blocked by CSC guardrail. Add a URL from an allowed CSC domain instead."


def add_pdf_knowledge(pdf_file, official_url, cloud_consent=False, human_reviewed=False):

    if not cloud_consent:
        return "Knowledge was not stored because cloud storage/embedding is not enabled."

    if not human_reviewed:
        return "Knowledge was not stored because human review approval was not granted."

    if not official_url or not is_allowed_url(official_url):
        return f"Blocked by CSC guardrail. Use an allowed official URL as the PDF source: {allowed_domains_label()}."

    if not pdf_file:
        return "Choose a PDF file first."

    try:
        from pypdf import PdfReader

        reader = PdfReader(pdf_file)
        text = "\n".join(page.extract_text() or "" for page in reader.pages[:80])
    except Exception:
        return "PDF could not be read. Please upload a valid text-based official PDF."

    chunks = _chunk_text(text)
    if not chunks:
        return "No readable text was found in this PDF."

    stored = 0
    failed = 0
    for chunk in chunks[:40]:
        ok, _ = store_vector(chunk, source=official_url, human_reviewed=human_reviewed)
        if ok:
            stored += 1
        else:
            failed += 1

    return f"PDF knowledge ingested: {stored} chunks stored. {failed} chunks failed."


def index_csc_service_guides(cloud_consent=False, max_sites=None, human_reviewed=False):

    if not cloud_consent:
        return "Service guides were not indexed because DPDP cloud storage/embedding consent was not granted."

    if not human_reviewed:
        return "Service guides were not indexed because human review approval was not granted."

    stored = 0
    failed = 0
    visited = 0

    if max_sites is None:
        try:
            max_sites = int(setting("CSC_SERVICE_INDEX_LIMIT", "12"))
        except ValueError:
            max_sites = 12

    for url in service_urls()[:max_sites]:
        visited += 1
        pages = crawl_website(url, max_pages=3)
        if not pages:
            failed += 1
            continue

        for page in pages:
            ok, _ = store_vector(page["content"], source=page["url"], human_reviewed=human_reviewed)
            if ok:
                stored += 1
            else:
                failed += 1

    return f"Indexed {stored} CSC service pages from {visited} official start URLs. {failed} pages failed."
