import os
from dotenv import load_dotenv
from openai import OpenAI
from docling.document import Document
from docling.loader import PdfLoader
from ..indesign_template_generation.rapport_creator import (
    ArticleImportance,
    choose_template,
)

# Load environment variables
load_dotenv()
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

JSON_OUTPUT_FOLDER = "processed_docs"


def save_docling_document(
    pdf_path: str, output_folder: str = JSON_OUTPUT_FOLDER
) -> str:
    """
    Create a Docling Document from a PDF and save it as a JSON file
    in an adjacent folder (default: 'processed_docs').

    Args:
        pdf_path (str): Path to the input PDF.
        output_folder (str): Folder where JSON files are stored.

    Returns:
        str: Path to the saved JSON file.
    """

    # Check that file exists
    if not os.path.exists(pdf_path):
        raise FileNotFoundError(f"File not found: {pdf_path}")

    # Check that file extension is .pdf (case-insensitive)
    if not pdf_path.lower().endswith(".pdf"):
        raise ValueError(f"File is not a PDF: {pdf_path}")

    # Load and process PDF
    loader = PdfLoader(pdf_path)
    doc = loader.load()
    document = Document.from_loader(doc)

    # Ensure output folder exists (adjacent to the PDF)
    base_dir = "."
    save_dir = os.path.join(base_dir, output_folder)
    os.makedirs(save_dir, exist_ok=True)

    # Define output filename (same name, .json extension)
    base_name = os.path.splitext(os.path.basename(pdf_path))[0]
    json_path = os.path.join(save_dir, f"{base_name}.json")

    # Save the document as JSON
    document.save_json(json_path)

    print(f"✅ Saved Docling document as JSON: {json_path}")
    return json_path


def load_docling_document(
    pdf_path: str, output_folder: str = JSON_OUTPUT_FOLDER
) -> Document:
    """
    Load a Docling document, either from an existing JSON serialization
    or by creating and saving it from the PDF if not already processed.

    Returns:
        Document: The loaded Docling Document object.
    """
    # Build the expected JSON path
    base_dir = "."
    save_dir = os.path.join(base_dir, output_folder)
    base_name = os.path.splitext(os.path.basename(pdf_path))[0]
    json_path = os.path.join(save_dir, f"{base_name}.json")

    # ✅ If JSON already exists → load it
    if os.path.exists(json_path):
        print(f"🔁 Found existing serialized Docling document: {json_path}")
        return Document.load_json(json_path)

    # 🚀 Otherwise → create it using save_docling_document()
    print(f"🆕 No JSON found, processing PDF: {pdf_path}")
    save_docling_document(pdf_path, output_folder)
    return Document.load_json(json_path)


# Extract number of pages from Docling Document
def extract_num_pages_docling(docling_document: Document) -> int:
    return len(docling_document.pages)


# Summarize with GPT-5-Nano
def summarize_pdf_docling(
    docling_document: Document,
    desired_text_length: int,
    model: str = "gpt-5-nano",
    temperature: float = 0.5,
    max_output_tokens: int = 2000,
) -> str:
    text = docling_document.get_text()

    # Handle long documents: truncate if needed
    if len(text) > 50000:
        text = text[:50000] + "\n\n[Note: Text truncated for summarization.]"

    response = client.chat.completions.create(
        model=model,
        messages=[
            {
                "role": "system",
                "content": "You are an expert summarizer of complex PDF documents.",
            },
            {
                "role": "user",
                "content": f"Summarize this document:\n{text}, the resulting summary should be around {desired_text_length} words.",
            },
        ],
        temperature=temperature,
        max_output_tokens=max_output_tokens,
    )

    return response.choices[0].message.content.strip()
