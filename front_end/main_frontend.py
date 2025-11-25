# streamlit_document_summarizer_frontend.py
"""
Frontend-only Streamlit UI for summarizing multiple documents.
Backend summarization is intentionally abstracted — plug in your own API call
inside `summarize_via_api(...)`.

How to run:
  pip install streamlit
  streamlit run streamlit_document_summarizer_frontend.py

Optional extras if you want to test the mock summarizer (no backend):
  - Works on .txt/.md files only (reads text client-side) just to demo the UI

What this UI does:
  - Lets you upload multiple files (txt/md/pdf/docx)
  - Pick a target word count
  - Click "Summarize" to call your backend (or a mock summarizer)
  - Shows the resulting summary
  - Lets you download the summary as a .txt file
"""

from __future__ import annotations

import re
from datetime import datetime
from typing import Iterable, List

import sys, os, docling
import tempfile

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import streamlit as st

from I_love_chatgpt.chatgpt import summarize_documents_parallel, parse_last_year_pdf

# -------------------------------
# Page Config
# -------------------------------
st.set_page_config(page_title="Document Summarizer", page_icon="📝", layout="wide")

st.title("📝 Document Summarizer v1")
st.caption(
    "Upload multiple documents, choose a target word count, generate a combined summary, and save it as .txt. Backend is abstracted."
)

# -------------------------------
# Sidebar Controls
# -------------------------------
with st.sidebar:
    st.header("Settings")
    target_words: int = st.slider(
        "Target words", min_value=50, max_value=500, value=200, step=10
    )
    st.divider()
    st.markdown(
        "Welcome to the v1 of our summarizer app\nThe following files are supported: PDF"
    )

# -------------------------------
# File Uploader
# -------------------------------
uploaded_files = st.file_uploader(
    "Upload one or more files",
    type=["pdf"],
    accept_multiple_files=True,
)

uploaded_last_year_pdf = st.file_uploader(
    "Upload last year's PDF",
    type=["pdf"],
    accept_multiple_files=False, # we want only one file
)   


def default_filename(prefix: str = "summary", word_count: int = 200) -> str:
    ts = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    return f"{prefix}_{word_count}w_{ts}.txt"


# -------------------------------
# UI Layout
# -------------------------------
left, right = st.columns([1, 1])

with left:
    st.subheader("Files")
    if uploaded_files:
        total_bytes = sum(
            getattr(f, "size", 0) or len(f.getvalue()) for f in uploaded_files
        )
        mb = total_bytes / (1024 * 1024)
        st.write(f"{len(uploaded_files)} file(s) • {mb:.2f} MB")
        for f in uploaded_files:
            st.caption(f"• {f.name}")
    else:
        st.info("No files selected yet.")

    if uploaded_last_year_pdf:
        st.divider()
        st.subheader("Last Year's Report")
        st.caption(f"• {uploaded_last_year_pdf.name}")

        total_bytes = getattr(uploaded_last_year_pdf, "size", 0) or len(uploaded_last_year_pdf.getvalue()) 
        
        mb = total_bytes / (1024 * 1024)
        st.write(f"1 file(s) • {mb:.2f} MB")
        st.caption(f"• {uploaded_last_year_pdf.name}")
        
        go_last_year = st.button("Summarize Last Year", type="primary", use_container_width=True)
        
        if go_last_year:
            if not uploaded_last_year_pdf:
                st.error("Please add at least one file.")
            else:
                pdf_bytes_last_year = uploaded_last_year_pdf.getvalue()
                with st.spinner(f"Parsing last year's report..."):
                    try:
                        results = parse_last_year_pdf(
                            pdf_bytes=pdf_bytes_last_year   ,
                        )
                       
                    except NotImplementedError as e:
                        st.warning(str(e))
                    except Exception as e:
                        st.error(f"Failed to summarize: {e}")

    go = st.button("Summarize", type="primary", use_container_width=True)

with right:
    st.subheader("Summary")
    if "summary" not in st.session_state:
        st.session_state.summary = ""

    if go:
        if not uploaded_files:
            st.error("Please add at least one file.")
        else:
            pdf_bytes_list = []
            pdf_paths = []

            for uploaded_file in uploaded_files:
                pdf_bytes = uploaded_file.getvalue()
                pdf_bytes_list.append(pdf_bytes)

                # Save uploaded PDF to a temporary file
                tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".pdf")
                tmp.write(pdf_bytes)
                tmp.flush()
                pdf_paths.append(tmp.name)
                tmp.close()

            with st.spinner(f"Analyzing and summarizing {len(uploaded_files)} documents in parallel..."):
                try:
                    results = summarize_documents_parallel(
                        pdf_bytes_list=pdf_bytes_list,
                        target_words=target_words,
                        pdf_paths=pdf_paths,
                    )
                    st.session_state.summary = "\n\n" + ("-" * 40) + "\n\n".join(results)
                except NotImplementedError as e:
                    st.warning(str(e))
                except Exception as e:
                    st.error(f"Failed to summarize: {e}")

    summary_text = st.session_state.summary
    st.text_area(
        "Summary", value=summary_text, height=260, label_visibility="collapsed"
    )

    col_a, col_b = st.columns(2)
    with col_a:
        filename = default_filename(word_count=target_words)
        st.download_button(
            label="💾 Download .txt",
            file_name=filename,
            data=summary_text.encode("utf-8"),
            mime="text/plain",
            use_container_width=True,
            disabled=not bool(summary_text),
        )
    with col_b:
        if summary_text:
            st.write(f"Words: {len(summary_text.split())}")
        else:
            st.write("Words: 0")

st.divider()
st.caption("Frontend only — connect your backend in `summarize_via_api()`.")
