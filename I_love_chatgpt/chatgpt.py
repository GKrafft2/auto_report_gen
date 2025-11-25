import os
import io
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

def parse_last_year_pdf(pdf_bytes: bytes, ):
    docling_doc = load_docling_document_cached(pdf_bytes)

    # 2. Chunk the document
    chunker = HierarchicalChunker()
    chunks = chunker.chunk(docling_doc)

    # Use a dictionary to group text by header
    # Key = Header String, Value = List of text strings
    grouped_content = defaultdict(list)

    for chunk in chunks:
        # Generate the header path string
        header = " > ".join(chunk.meta.headings) if chunk.meta.headings else "No Header"
        
        # Append the current chunk's text to the list for this header
        grouped_content[header].append(chunk.text)

    # Iterate through the grouped content and print
    for header, text_parts in grouped_content.items():
        # Fuse the parts together with a newline (or space, depending on preference)
        full_text = "\n".join(text_parts)
        
        print(f"--- Section: {header} ---")
        print(full_text)
        print("\n")
    


def load_docling_document_cached(pdf_bytes: bytes) -> DoclingDocument:
    """
    Convert using Docling only once (content-hash cache).
    """
    _ensure_cache_dir()
    key = _hash_bytes(pdf_bytes)
    json_path = os.path.join(CACHE_DIR, f"{key}.json")

    if os.path.exists(json_path):
        print(f"[Docling cache] HIT → {json_path}")
        return DoclingDocument.load_from_json(json_path)

    print(f"[Docling cache] MISS → Converting with Docling…")
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
        print("🔵 Using direct GPT PDF ingestion (fast path)")

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
    print("🟣 Using Docling conversion (complex or scanned PDF)")
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
                print(f"Document {index} generated an exception: {exc}")
                results[index] = f"Error summarizing document: {exc}"

    return results
