import hashlib
import re
from urllib.parse import urlparse

from crawler import crawl_website
from database import store_vector
from guardrails import allowed_domains_label, is_allowed_url, setting
from service_catalog import service_urls


DEFAULT_PARENT_CHUNK_SIZE = 2200
DEFAULT_PARENT_OVERLAP = 220
DEFAULT_CHILD_CHUNK_SIZE = 700
DEFAULT_CHILD_OVERLAP = 140


def _setting_int(name, default):

    try:
        return int(setting(name, str(default)))
    except ValueError:
        return default


def _clean_text(text):

    lines = []
    for raw_line in (text or "").splitlines():
        line = " ".join(raw_line.split())
        if line:
            lines.append(line)

    if not lines:
        return " ".join((text or "").split())

    return "\n".join(lines)


def _split_recursively(text, chunk_size, overlap):

    clean = _clean_text(text)
    if not clean:
        return []

    chunks = []
    units = re.split(r"(?<=[.!?।])\s+|\n+", clean)

    expanded_units = []
    for unit in units:
        unit = unit.strip()
        if not unit:
            continue
        if len(unit) <= chunk_size:
            expanded_units.append(unit)
            continue

        words = unit.split()
        current_words = []
        current_length = 0
        for word in words:
            extra = len(word) + (1 if current_words else 0)
            if current_words and current_length + extra > chunk_size:
                expanded_units.append(" ".join(current_words))
                current_words = []
                current_length = 0
            current_words.append(word)
            current_length += extra
        if current_words:
            expanded_units.append(" ".join(current_words))

    current = ""
    for unit in expanded_units:
        next_text = f"{current} {unit}".strip() if current else unit
        if len(next_text) > chunk_size and current:
            chunks.append(current)
            tail = current[-overlap:].strip() if overlap else ""
            current = f"{tail} {unit}".strip() if tail else unit
        else:
            current = next_text

    if current:
        chunks.append(current)

    deduped = []
    for chunk in chunks:
        if chunk and chunk not in deduped:
            deduped.append(chunk)

    return deduped


def _chunk_text(text, max_chars=3500):

    return _split_recursively(text, max_chars, max(0, max_chars // 8))


def _source_category(source, text=""):

    host = urlparse(source or "").netloc.lower()
    haystack = f"{host} {text[:500]}".lower()
    categories = (
        ("pm_kisan", ("pmkisan", "pm kisan", "farmer", "kisan")),
        ("pan", ("pan", "protean", "tinpan", "utiitsl", "income tax")),
        ("digipay", ("digipay", "cash withdrawal", "aeps", "csccloud")),
        ("e_shram", ("eshram", "e-shram", "labour", "shram")),
        ("ayushman", ("ayushman", "pmjay", "nha")),
        ("digital_seva", ("digitalseva", "digital seva", "csc")),
    )

    for category, terms in categories:
        if any(term in haystack for term in terms):
            return category

    return "general"


def _doc_id(source, text):

    fingerprint = f"{source}\n{text[:4000]}".encode("utf-8", "ignore")
    return hashlib.sha256(fingerprint).hexdigest()[:16]


def _metadata_prefix(metadata):

    return (
        f"Source: {metadata['source']}\n"
        f"Document ID: {metadata['document_id']}\n"
        f"Parent Chunk: {metadata['parent_id']}\n"
        f"Child Chunk: {metadata['chunk_id']}\n"
        f"Category: {metadata['category']}\n\n"
    )


def _prepare_index_chunks(text, source, title="", max_chunks=None):

    clean = _clean_text(text)
    if not clean:
        return []

    parent_size = _setting_int("PARENT_CHUNK_SIZE", DEFAULT_PARENT_CHUNK_SIZE)
    parent_overlap = _setting_int("PARENT_CHUNK_OVERLAP", DEFAULT_PARENT_OVERLAP)
    child_size = _setting_int("CHILD_CHUNK_SIZE", DEFAULT_CHILD_CHUNK_SIZE)
    child_overlap = _setting_int("CHILD_CHUNK_OVERLAP", DEFAULT_CHILD_OVERLAP)
    max_chunks = max_chunks or _setting_int("MAX_CHUNKS_PER_DOCUMENT", 80)
    document_id = _doc_id(source, clean)
    category = _source_category(source, clean)

    prepared = []
    parents = _split_recursively(clean, parent_size, parent_overlap)
    for parent_index, parent_text in enumerate(parents, start=1):
        parent_id = f"{document_id}-p{parent_index:03d}"
        children = _split_recursively(parent_text, child_size, child_overlap)
        for child_index, child_text in enumerate(children, start=1):
            chunk_index = len(prepared)
            chunk_id = f"{parent_id}-c{child_index:03d}"
            metadata = {
                "source": source,
                "title": title,
                "document_id": document_id,
                "parent_id": parent_id,
                "chunk_id": chunk_id,
                "chunk_index": chunk_index,
                "category": category,
                "chunking": "parent_child_recursive",
            }
            prepared.append(
                {
                    "content": _metadata_prefix(metadata) + child_text,
                    "metadata": metadata,
                }
            )
            if len(prepared) >= max_chunks:
                return prepared

    return prepared


def _store_chunks(chunks, human_reviewed=False):

    stored = 0
    failed = 0
    last_error = ""
    for chunk in chunks:
        metadata = chunk["metadata"]
        ok, message = store_vector(
            chunk["content"],
            source=metadata["source"],
            human_reviewed=human_reviewed,
            metadata=metadata,
            document_id=metadata["document_id"],
            parent_id=metadata["parent_id"],
            chunk_id=metadata["chunk_id"],
            chunk_index=metadata["chunk_index"],
            category=metadata["category"],
        )
        if ok:
            stored += 1
        else:
            failed += 1
            last_error = message

    return stored, failed, last_error


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
        last_error = ""

        for page in pages:
            chunks = _prepare_index_chunks(page["content"], page["url"], title=page.get("title", ""))
            page_stored, page_failed, page_error = _store_chunks(chunks, human_reviewed=human_reviewed)
            stored += page_stored
            failed += page_failed
            last_error = page_error or last_error

        detail = f" Last error: {last_error}" if last_error and failed else ""
        return f"Website knowledge indexed: {stored} semantic chunks stored. {failed} chunks failed.{detail}"

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

    chunks = _prepare_index_chunks(text, official_url, title=getattr(pdf_file, "name", "Official PDF"), max_chunks=80)
    if not chunks:
        return "No readable text was found in this PDF."

    stored, failed, last_error = _store_chunks(chunks, human_reviewed=human_reviewed)

    detail = f" Last error: {last_error}" if last_error and failed else ""
    return f"PDF knowledge ingested: {stored} semantic chunks stored. {failed} chunks failed.{detail}"


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
            chunks = _prepare_index_chunks(page["content"], page["url"], title=page.get("title", ""))
            page_stored, page_failed, _ = _store_chunks(chunks, human_reviewed=human_reviewed)
            stored += page_stored
            failed += page_failed

    return f"Indexed {stored} semantic chunks from {visited} official start URLs. {failed} chunks failed."
