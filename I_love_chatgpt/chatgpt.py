import os
import re
import time
import io
import logging

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)
import tempfile
import hashlib
import concurrent.futures

from dotenv import load_dotenv
from openai import OpenAI

from pypdf import PdfReader
from docling.document_converter import DocumentConverter
from docling_core.types.doc import DoclingDocument

from docling.chunking import HierarchicalChunker
from collections import defaultdict

from docling.datamodel.accelerator_options import AcceleratorDevice, AcceleratorOptions

# Configure accelerator options for GPU
accelerator_options = AcceleratorOptions(
    device=AcceleratorDevice.CUDA,  # or AcceleratorDevice.AUTO
)

# Load env
load_dotenv()
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# Persistent Docling cache
CACHE_DIR = os.path.join(os.path.dirname(__file__), "docling_cache")

# Heavy converter for scanned/complex PDFs
_heavy_converter = DocumentConverter()  # load OCR/layout models upfront


def _hash_bytes(pdf_bytes: bytes) -> str:
    h = hashlib.sha256()
    h.update(pdf_bytes)
    return h.hexdigest()


def _ensure_cache_dir():
    os.makedirs(CACHE_DIR, exist_ok=True)


# -------------------------------------------------------
# 1. LIGHTWEIGHT PDF PROBE (fast complexity detection)
# -------------------------------------------------------


def pdf_has_text(pdf_bytes: bytes, min_chars=300) -> bool:
    """
    Check if the PDF contains enough digital text to be considered non-scanned.
    """
    try:
        reader = PdfReader(io.BytesIO(pdf_bytes))
        extracted = ""
        for page in reader.pages[:3]:  # sample first 3 pages
            t = page.extract_text() or ""
            extracted += t
        return len(extracted.strip()) >= min_chars
    except Exception:
        return False


def pdf_character_count(pdf_bytes: bytes) -> int:
    """
    Extract text cheaply & count characters.
    """
    try:
        reader = PdfReader(io.BytesIO(pdf_bytes))
        text = ""
        for page in reader.pages:
            t = page.extract_text() or ""
            text += t
        return len(text)
    except Exception:
        return 0


def pdf_is_small(pdf_bytes: bytes, max_size_mb=3) -> bool:
    return len(pdf_bytes) <= max_size_mb * 1024 * 1024


def pdf_is_simple_enough_for_gpt(pdf_bytes: bytes) -> bool:
    """
    Decide whether we can skip Docling entirely and send PDF directly to GPT.
    """
    if not pdf_is_small(pdf_bytes):
        return False
    if not pdf_has_text(pdf_bytes):
        return False

    chars = pdf_character_count(pdf_bytes)

    # GPT can handle ~40K chars reliably
    if chars > 40_000:
        return False

    return True


# -------------------------------------------------------
# 2. DOC LING CONVERSION (cached)
# -------------------------------------------------------


def _convert_bytes_to_docling(pdf_bytes: bytes) -> DoclingDocument:
    with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
        tmp.write(pdf_bytes)
        tmp_path = tmp.name

    try:
        result = _heavy_converter.convert(tmp_path)
        return result.document
    finally:
        try:
            os.remove(tmp_path)
        except:
            pass

import pycountry
from collections import defaultdict
from docling.chunking import HierarchicalChunker
from docling.datamodel.base_models import DocItemLabel

import pycountry
from collections import defaultdict
from docling.chunking import HierarchicalChunker
from docling.datamodel.base_models import DocItemLabel

# --- HELPER: Country Detection ---
def is_country_header(text: str) -> bool:
    if not text or len(text.strip()) < 2: 
        return False
    clean_text = text.strip()
    try:
        pycountry.countries.search_fuzzy(clean_text)
        return True
    except (LookupError, Exception):
        return False

# --- PRE-PROCESSOR: Fuse Headers ---
def fuse_consecutive_headers(doc):
    texts = doc.texts
    i = 0
    
    # Iterate through items
    while i < len(texts) - 1:
        current_item = texts[i]
        next_item = texts[i+1]

        # 1. Check for consecutive headers
        if (current_item.label == DocItemLabel.SECTION_HEADER and 
            next_item.label == DocItemLabel.SECTION_HEADER):
            
            # Check page consistency
            page_current = current_item.prov[0].page_no if current_item.prov else -1
            page_next = next_item.prov[0].page_no if next_item.prov else -2
            
            if page_current == page_next:
                # 2. Check if the SECOND header is a Country
                if is_country_header(next_item.text):
                    
                    # --- THE FIX IS HERE ---
                    
                    # Instead of keeping the first one, we keep the SECOND one
                    # because the body text is likely attached (children) to the second one.
                    
                    # Update the Second Item (The Anchor)
                    next_item.text = f"{current_item.text} - {next_item.text}"
                    
                    # "Nuke" the First Item (The Label)
                    current_item.text = ""
                    current_item.label = DocItemLabel.TEXT
                    
                    # Skip ahead since we processed this pair
                    i += 2
                    continue

        i += 1
        
    return doc

def parse_last_year_pdf(pdf_bytes: bytes):
    docling_doc = load_docling_document_cached(pdf_bytes)

    # Apply the fix before chunking
    docling_doc = fuse_consecutive_headers(docling_doc)

    chunker = HierarchicalChunker()
    chunks = chunker.chunk(docling_doc)

    grouped_content = defaultdict(list)

    for chunk in chunks:
        header = " > ".join(chunk.meta.headings) if chunk.meta.headings else "No Header"
        
        # Filter out empty strings that might result from the nuked header
        if chunk.text.strip():
            grouped_content[header].append(chunk.text)

    logger.debug("--- Unique Headers Detected ---")
    for h in grouped_content.keys():
        logger.debug(f"| {h}")

    return grouped_content
    


def load_docling_document_cached(pdf_bytes: bytes) -> DoclingDocument:
    """
    Convert using Docling only once (content-hash cache).
    """
    _ensure_cache_dir()
    key = _hash_bytes(pdf_bytes)
    json_path = os.path.join(CACHE_DIR, f"{key}.json")

    if os.path.exists(json_path):
        logger.info(f"[Docling cache] HIT → {json_path}")
        return DoclingDocument.load_from_json(json_path)

    logger.info(f"[Docling cache] MISS → Converting with Docling…")
    doc = _convert_bytes_to_docling(pdf_bytes)
    doc.save_as_json(json_path)
    return doc


# -------------------------------------------------------
# 3. PUBLIC HYBRID API
# -------------------------------------------------------


def load_document_hybrid(pdf_bytes: bytes):
    """
    Returns either:
        - { "mode": "gpt",  "bytes": pdf_bytes }
        - { "mode": "docling", "doc": DoclingDocument }

    depending on complexity.
    """
    if pdf_is_simple_enough_for_gpt(pdf_bytes):
        return {"mode": "gpt", "bytes": pdf_bytes}

    doc = load_docling_document_cached(pdf_bytes)
    return {"mode": "docling", "doc": doc}


# -------------------------------------------------------
# 4. SUMMARIZATION
# -------------------------------------------------------


def summarize_document_hybrid(
    pdf_bytes: bytes, target_words: int, pdf_path: str
) -> str:
    """
    Automatically chooses the best summarization workflow.
    """

    route = load_document_hybrid(pdf_bytes)

    # ---------------------------
    # DIRECT GPT PDF HANDLING
    # ---------------------------
    if route["mode"] == "gpt":
        logger.info("🔵 Using direct GPT PDF ingestion (fast path)")

        # Upload the file to OpenAI first
        file = client.files.create(
            file=open(pdf_path, "rb"),
            purpose="user_data",
        )

        response = client.chat.completions.create(
            model="gpt-5-nano",
            messages=[
                {"role": "system", "content": "You are an expert document summarizer."},
                {
                    "role": "user",
                    "content": [
                        {"type": "input_file",
                        "file_id": file.id,},
                        {"type": "input_text", "text": "Please summarize the attached PDF document. Target length: {target_words} words."}
                    ]
                },
            ],
        )
        return response.choices[0].message.content.strip()

    # ---------------------------
    # DOCLING PATH
    # ---------------------------
    logger.info("🟣 Using Docling conversion (complex or scanned PDF)")
    doc = route["doc"]
    text = doc.export_to_text()

    # truncate very long docs
    if len(text) > 50_000:
        text = text[:50_000] + "\n\n[Note: truncated for summarization]"

    response = client.chat.completions.create(
        model="gpt-5-nano",
        messages=[
            {"role": "system", "content": "You are an expert document summarizer."},
            {
                "role": "user",
                "content": f"Summarize the following document:\n{text}\n\nTarget: {target_words} words",
            },
        ],
    )
    return response.choices[0].message.content.strip()


# -------------------------------------------------------
# 5. PARALLEL SUMMARIZATION
# -------------------------------------------------------


def summarize_documents_parallel(
    pdf_bytes_list: list[bytes], target_words: int, pdf_paths: list[str] = None
) -> list[str]:
    """
    Summarizes multiple documents in parallel.
    """
    if pdf_paths is None:
        pdf_paths = [f"doc_{i}.pdf" for i in range(len(pdf_bytes_list))]

    results = [None] * len(pdf_bytes_list)

    # We can use a ThreadPoolExecutor because the operations are largely I/O bound
    # (network requests to OpenAI) or run in subprocesses (Docling).
    # However, Docling might be CPU intensive.
    # For now, we'll use a reasonable max_workers.
    max_workers = min(10, len(pdf_bytes_list))

    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_to_index = {
            executor.submit(
                summarize_document_hybrid, pdf_bytes, target_words, pdf_path
            ): i
            for i, (pdf_bytes, pdf_path) in enumerate(zip(pdf_bytes_list, pdf_paths))
        }

        for future in concurrent.futures.as_completed(future_to_index):
            index = future_to_index[future]
            try:
                summary = future.result()
                results[index] = summary
            except Exception as exc:
                logger.error(f"Document {index} generated an exception: {exc}")
                results[index] = f"Error summarizing document: {exc}"

    return results


def generate_section_summary(header: str, previous_text: str, new_pdf_bytes_list: list[bytes], manual_comments: str = "") -> str:
    """
    Generates a new section summary based on the previous year's text and new linked PDF resources.
    """
    logger.info(f"--- Generating Summary for Section: {header} ---")
    
    # 1. Process new resources
    new_content_text = ""
    for i, pdf_bytes in enumerate(new_pdf_bytes_list):
        try:
            doc = load_docling_document_cached(pdf_bytes)
            text = doc.export_to_text()
            new_content_text += f"\n--- New Resource {i+1} ---\n{text}\n"
        except Exception as e:
            logger.error(f"Error processing resource {i+1}: {e}")
            new_content_text += f"\n--- New Resource {i+1} (Error) ---\nFailed to process.\n"

    # 2. Construct Prompt
    # Calculate target word count based on previous text
    previous_word_count = len(previous_text.split()) if previous_text else 0
    
    # Calculate target sentence count
    # Simple split by period, question mark, exclamation mark followed by space or end of string
    previous_sentence_count = len(re.split(r'[.!?]+', previous_text)) if previous_text else 0
    # Adjust for empty strings from split
    if previous_text:
        previous_sentence_count = len([s for s in re.split(r'[.!?]+', previous_text) if s.strip()])

    target_len_str = f"approximately {previous_word_count} words and {previous_sentence_count} sentences" if previous_word_count > 0 else "appropriate length"

    # Determine instructions based on whether new content exists
    if not new_content_text.strip():
        # Case: No new info -> Reformulate generic
        instructions = f"""
1. Reformulate the content for the section "{header}" based on the previous year's text.
2. Remove any specific references to the previous year (dates, specific past events).
3. Maintain a generic tone indicating continuity (e.g., "we are continuing and happy to support...").
4. Maintain the tone and style of the previous year's content, the answer MUST be in english.
5. Write from Ceres's point of view. Avoid bragging about the generosity of donations.
6. You may include a sentence expressing how happy Ceres is to support the initiatives if appropriate.
7. The response length MUST be {target_len_str}.
8. Do not include the header in the output, just the body text.
"""
        new_content_display = "(No new information provided)"
    else:
        # Case: New info exists -> Synthesize
        instructions = f"""
1. Write the new content for the section "{header}".
2. Maintain the tone and style of the previous year's content, the answer MUST be in english.
3. Write from Ceres's point of view. Avoid bragging about the generosity of donations.
4. You may include a sentence expressing how happy Ceres is to support the initiatives if appropriate.
5. The response length MUST be {target_len_str}.
6. Synthesize the information from the "New Input Data".
7. If the new data contradicts the old data, prioritize the new data.
7. If the new data contradicts the old data, prioritize the new data.
8. Do not include the header in the output, just the body text.
"""
        new_content_display = new_content_text

    # Add manual comments to instructions if present
    manual_comments_section = ""
    if manual_comments.strip():
        manual_comments_section = f"""
--- MANUAL COMMENTS / INSTRUCTIONS ---
{manual_comments}
--------------------------------------
"""
        instructions += "\n9. IMPORTANT: Follow the specific instructions provided in the 'MANUAL COMMENTS / INSTRUCTIONS' section above."

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

    logger.debug("\n[DEBUG] Generated Prompt:\n")
    logger.debug(prompt)
    logger.debug("\n[DEBUG] End Prompt\n")

    # 3. Call OpenAI
    try:
        logger.info(f"[DEBUG] Sending request to OpenAI for section '{header}'...")
        start_time = time.time()
        
        response = client.chat.completions.create(
            model="gpt-5-mini",
            messages=[
                {"role": "system", "content": "You are a helpful assistant that writes report sections."},
                {"role": "user", "content": prompt},
            ],
        )
        
        end_time = time.time()
        duration = end_time - start_time
        
        # Extract token usage if available
        usage = response.usage
        input_tokens = usage.prompt_tokens if usage else "N/A"
        output_tokens = usage.completion_tokens if usage else "N/A"
        total_tokens = usage.total_tokens if usage else "N/A"
        
        logger.info(f"[DEBUG] OpenAI Request Completed in {duration:.2f} seconds.")
        logger.info(f"[DEBUG] Token Usage - Input: {input_tokens}, Output: {output_tokens}, Total: {total_tokens}")
        
        return response.choices[0].message.content.strip()
    except Exception as e:
        return f"Error generating summary: {e}"
