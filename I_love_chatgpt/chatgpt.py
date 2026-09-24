import hashlib
import logging
import os
import re
import tempfile
import time
from collections import defaultdict

import pycountry
from docling.chunking import HierarchicalChunker
from docling.datamodel.base_models import DocItemLabel
from docling.document_converter import DocumentConverter
from docling_core.types.doc import DoclingDocument
from dotenv import load_dotenv
from openai import OpenAI

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

load_dotenv()
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# Persistent Docling cache
CACHE_DIR = os.path.join(os.path.dirname(__file__), "docling_cache")

# Load OCR/layout models upfront
_converter = DocumentConverter()


# -------------------------------------------------------
# 1. DOCLING CONVERSION (cached)
# -------------------------------------------------------


def _hash_bytes(pdf_bytes: bytes) -> str:
    return hashlib.sha256(pdf_bytes).hexdigest()


def _convert_bytes_to_docling(pdf_bytes: bytes) -> DoclingDocument:
    with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
        tmp.write(pdf_bytes)
        tmp_path = tmp.name

    try:
        return _converter.convert(tmp_path).document
    finally:
        try:
            os.remove(tmp_path)
        except OSError:
            pass


def load_docling_document_cached(pdf_bytes: bytes) -> DoclingDocument:
    """
    Convert using Docling only once (content-hash cache).
    """
    os.makedirs(CACHE_DIR, exist_ok=True)
    json_path = os.path.join(CACHE_DIR, f"{_hash_bytes(pdf_bytes)}.json")

    if os.path.exists(json_path):
        logger.info(f"[Docling cache] HIT → {json_path}")
        return DoclingDocument.load_from_json(json_path)

    logger.info("[Docling cache] MISS → Converting with Docling…")
    doc = _convert_bytes_to_docling(pdf_bytes)
    doc.save_as_json(json_path)
    return doc


def extract_clean_text(doc: DoclingDocument) -> str:
    """
    Extracts text from the document, filtering out noise like headers, footers, and captions.
    """
    allowed_labels = {
        DocItemLabel.TEXT,
        DocItemLabel.SECTION_HEADER,
        DocItemLabel.LIST_ITEM,
        DocItemLabel.TABLE,
        DocItemLabel.CODE,
        DocItemLabel.FORMULA,
    }
    return "\n".join(item.text for item in doc.texts if item.label in allowed_labels)


# -------------------------------------------------------
# 2. LAST YEAR'S REPORT PARSING
# -------------------------------------------------------


def is_country_header(text: str) -> bool:
    if not text or len(text.strip()) < 2:
        return False
    try:
        pycountry.countries.search_fuzzy(text.strip())
        return True
    except LookupError:
        return False


def fuse_consecutive_headers(doc: DoclingDocument) -> DoclingDocument:
    """
    Merges a section header immediately followed by a country header on the same
    page (e.g. "Project X" / "Kenya") into a single "Project X - Kenya" header.
    """
    texts = doc.texts
    i = 0

    while i < len(texts) - 1:
        current_item = texts[i]
        next_item = texts[i + 1]

        if (
            current_item.label == DocItemLabel.SECTION_HEADER
            and next_item.label == DocItemLabel.SECTION_HEADER
        ):
            page_current = current_item.prov[0].page_no if current_item.prov else -1
            page_next = next_item.prov[0].page_no if next_item.prov else -2

            if page_current == page_next and is_country_header(next_item.text):
                # Keep the second header, since the body text is attached to it,
                # and blank out the first one.
                next_item.text = f"{current_item.text} - {next_item.text}"
                current_item.text = ""
                current_item.label = DocItemLabel.TEXT
                i += 2
                continue

        i += 1

    return doc


def parse_last_year_pdf(pdf_bytes: bytes) -> dict[str, list[str]]:
    docling_doc = fuse_consecutive_headers(load_docling_document_cached(pdf_bytes))

    grouped_content = defaultdict(list)
    for chunk in HierarchicalChunker().chunk(docling_doc):
        header = " > ".join(chunk.meta.headings) if chunk.meta.headings else "No Header"
        # Skip empty chunks left over from the fused headers
        if chunk.text.strip():
            grouped_content[header].append(chunk.text)

    logger.debug("--- Unique Headers Detected ---")
    for h in grouped_content:
        logger.debug(f"| {h}")

    return grouped_content


# -------------------------------------------------------
# 3. SECTION GENERATION
# -------------------------------------------------------


def generate_section_summary(
    header: str, previous_text: str, new_pdf_bytes_list: list[bytes], manual_comments: str = ""
) -> str:
    """
    Generates a new section summary based on the previous year's text and new linked PDF resources.
    """
    logger.info(f"--- Generating Summary for Section: {header} ---")

    # 1. Process new resources
    new_content_text = ""
    for i, pdf_bytes in enumerate(new_pdf_bytes_list):
        try:
            text = extract_clean_text(load_docling_document_cached(pdf_bytes))
            new_content_text += f"\n--- New Resource {i+1} ---\n{text}\n"
        except Exception as e:
            logger.error(f"Error processing resource {i+1}: {e}")
            new_content_text += f"\n--- New Resource {i+1} (Error) ---\nFailed to process.\n"

    # 2. Construct Prompt
    # Target length mirrors the previous year's word and sentence counts
    previous_word_count = len(previous_text.split()) if previous_text else 0
    previous_sentence_count = len([s for s in re.split(r"[.!?]+", previous_text) if s.strip()])

    target_len_str = (
        f"approximately {previous_word_count} words and {previous_sentence_count} sentences"
        if previous_word_count > 0
        else "appropriate length"
    )

    if not new_content_text.strip():
        # No new info -> generic reformulation
        instructions = f"""
1. Reformulate the content for the section "{header}" based on the previous year's text.
2. Remove any specific references to the previous year (dates, specific past events).
3. Maintain a generic tone indicating continuity (e.g., "we are continuing and happy to support...").
4. Maintain the tone and style of the previous year's content, the answer MUST be in english.
5. Write from Ceres's point of view. Avoid bragging about the generosity of donations.
6. You may include a sentence expressing how happy Ceres is to support the initiatives if appropriate.
7. The response length MUST be {target_len_str}.
8. Do not include the header in the output, just the body text.
9. Keep the content high-level and avoid unnecessary details.
10. STRICTLY FORBIDDEN: Do not mention any specific figures, numbers, or amounts of money.
"""
        new_content_display = "(No new information provided)"
    else:
        # New info exists -> synthesize
        instructions = f"""
1. Write the new content for the section "{header}".
2. Maintain the tone and style of the previous year's content, the answer MUST be in english.
3. Write from Ceres's point of view. Avoid bragging about the generosity of donations.
4. You may include a sentence expressing how happy Ceres is to support the initiatives if appropriate.
5. The response length MUST be {target_len_str}.
6. Synthesize the information from the "New Input Data".
7. If the new data contradicts the old data, prioritize the new data.
8. Do not include the header in the output, just the body text.
9. Keep the content high-level and avoid unnecessary details.
10. STRICTLY FORBIDDEN: Do not mention any specific figures, numbers, or amounts of money.
"""
        new_content_display = new_content_text

    manual_comments_section = ""
    if manual_comments.strip():
        manual_comments_section = f"""
--- MANUAL COMMENTS / INSTRUCTIONS ---
{manual_comments}
--------------------------------------
"""
        instructions += "11. IMPORTANT: Follow the specific instructions provided in the 'MANUAL COMMENTS / INSTRUCTIONS' section above.\n"

    prompt = f"""
You are an expert report writer. Your task is to write an updated section for a report based on the previous year's content and new input data.

SECTION HEADER: {header}

--- PREVIOUS YEAR'S CONTENT (For Style and Context) ---
{previous_text}
-------------------------------------------------------

--- NEW INPUT DATA (To be incorporated) ---
{new_content_display}
-------------------------------------------

{manual_comments_section}

INSTRUCTIONS:
{instructions}
"""

    logger.debug(f"Generated prompt:\n{prompt}")

    # 3. Call OpenAI
    try:
        logger.info(f"Sending request to OpenAI for section '{header}'...")
        start_time = time.time()

        response = client.chat.completions.create(
            model="gpt-6-luna",
            messages=[
                {"role": "system", "content": "You are a helpful assistant that writes report sections."},
                {"role": "user", "content": prompt},
            ],
        )

        duration = time.time() - start_time
        usage = response.usage
        logger.info(f"OpenAI request for '{header}' completed in {duration:.2f} seconds.")
        if usage:
            logger.info(
                f"Token usage - Input: {usage.prompt_tokens}, "
                f"Output: {usage.completion_tokens}, Total: {usage.total_tokens}"
            )

        return response.choices[0].message.content.strip()
    except Exception as e:
        return f"Error generating summary: {e}"
