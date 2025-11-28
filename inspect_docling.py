import sys
import os
import logging

# Add project root to path
sys.path.append(os.getcwd())

from I_love_chatgpt.chatgpt import load_docling_document_cached, extract_clean_text
from docling.datamodel.base_models import DocItemLabel

# Configure logging
logging.basicConfig(level=logging.INFO)

def inspect_pdf(pdf_path):
    if not os.path.exists(pdf_path):
        print(f"File not found: {pdf_path}")
        return

    with open(pdf_path, "rb") as f:
        pdf_bytes = f.read()

    print(f"Processing {pdf_path}...")
    doc = load_docling_document_cached(pdf_bytes)
    
    print("\n--- Document Items Analysis ---")
    label_counts = {}
    
    # Iterate over all texts/items
    # Note: doc.texts is a generator or list of items in reading order
    for item in doc.texts:
        label = item.label
        label_counts[label] = label_counts.get(label, 0) + 1
        
        # Print some examples of headers/footers to verify they are indeed noise
        if label in [DocItemLabel.PAGE_HEADER, DocItemLabel.PAGE_FOOTER, DocItemLabel.FOOTNOTE]:
            print(f"[{label}]: {item.text[:50]}...")

    print("\n--- Label Counts ---")
    for label, count in label_counts.items():
        print(f"{label}: {count}")

    print("\n--- Clean Text Extraction Test ---")
    clean_text = extract_clean_text(doc)
    print(f"Clean text length: {len(clean_text)}")
    print(f"Original text length: {len(doc.export_to_text())}")
    
    # Check if any forbidden labels leaked (should be impossible by definition of function, but good to see reduction)
    print(f"Reduction ratio: {len(clean_text) / len(doc.export_to_text()):.2f}")

if __name__ == "__main__":
    # Use one of the PDFs in the directory
    pdf_file = "07A_Caritas_rapport CERES 2024.pdf"
    inspect_pdf(pdf_file)
