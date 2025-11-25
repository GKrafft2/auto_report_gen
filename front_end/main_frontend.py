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

st.title("📝 Document Summarizer v2")
st.caption(
    "Two-step workflow: 1) Parse last year's report, 2) Upload new resources and link them to sections."
)

# -------------------------------
# Session State Init
# -------------------------------
if "step" not in st.session_state:
    st.session_state.step = 1
if "sections" not in st.session_state:
    st.session_state.sections = {}  # {header: [text_parts]}
if "section_links" not in st.session_state:
    st.session_state.section_links = {}

# -------------------------------
# Step 1: Upload & Parse Last Year's Report
# -------------------------------
if st.session_state.step == 1:
    st.header("Step 1: Upload Last Year's Report")
    
    uploaded_last_year = st.file_uploader(
        "Upload Last Year's PDF",
        type=["pdf"],
        key="uploader_last_year"
    )

    if uploaded_last_year:
        st.info(f"File uploaded: {uploaded_last_year.name}")
        
        if st.button("Parse Report", type="primary"):
            with st.spinner("Parsing last year's report..."):
                try:
                    # Call backend
                    sections = parse_last_year_pdf(uploaded_last_year.getvalue())
                    st.session_state.sections = sections
                    st.session_state.step = 2
                    st.rerun()
                except Exception as e:
                    st.error(f"Failed to parse: {e}")

# -------------------------------
# Step 2: Upload Resources & Link
# -------------------------------
elif st.session_state.step == 2:
    st.header("Step 2: Upload Resources & Link")
    
    col1, col2 = st.columns([1, 2])
    
    with col1:
        st.subheader("New Resources")
        uploaded_resources = st.file_uploader(
            "Upload New Resource Files",
            type=["pdf"],
            accept_multiple_files=True,
            key="uploader_resources"
        )
        
        resource_names = [f.name for f in uploaded_resources] if uploaded_resources else []
        
        if st.button("Start Over", type="secondary"):
            st.session_state.step = 1
            st.session_state.sections = {}
            st.session_state.section_links = {}
            st.rerun()

    with col2:
        st.subheader("Link Resources to Sections")
        
        if not st.session_state.sections:
            st.warning("No sections found in the previous report.")
        else:
            # Display sections and linking UI
            links = {}
            for header, text_parts in st.session_state.sections.items():
                # Preview text (first 200 chars)
                full_text = " ".join(text_parts)
                preview = full_text[:200] + "..." if len(full_text) > 200 else full_text
                
                with st.expander(f"Section: {header}", expanded=True):
                    st.caption(preview)
                    selected_files = st.multiselect(
                        f"Select resources for '{header}'",
                        options=resource_names,
                        key=f"link_{header}"
                    )
                    links[header] = selected_files
            
            st.divider()
            if st.button("Generate Report (Preview Links)", type="primary"):
                st.session_state.section_links = links
                st.success("Links saved! (Generation logic to be implemented)")
                st.json(links)

