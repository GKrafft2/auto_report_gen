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
import concurrent.futures

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import streamlit as st

from I_love_chatgpt.chatgpt import summarize_documents_parallel, parse_last_year_pdf, generate_section_summary

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
if "section_enabled" not in st.session_state:
    st.session_state.section_enabled = {}

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
                    # Initialize all sections as enabled by default
                    st.session_state.section_enabled = {h: True for h in sections.keys()}
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
            st.session_state.section_enabled = {}
            st.rerun()

    with col2:
        st.subheader("Link Resources to Sections")
        
        if not st.session_state.sections:
            st.warning("No sections found in the previous report.")
        else:
            # Select/Unselect All Buttons
            col_sel, col_unsel = st.columns(2)
            with col_sel:
                if st.button("Select All", use_container_width=True):
                    for h in st.session_state.sections.keys():
                        st.session_state.section_enabled[h] = True
                        st.session_state[f"enable_{h}"] = True
                    st.rerun()
            with col_unsel:
                if st.button("Unselect All", use_container_width=True):
                    for h in st.session_state.sections.keys():
                        st.session_state.section_enabled[h] = False
                        st.session_state[f"enable_{h}"] = False
                    st.rerun()

            # Display sections and linking UI
            links = {}
            enabled_status = {}
            
            for header, text_parts in st.session_state.sections.items():
                # Preview text (first 200 chars)
                full_text = " ".join(text_parts)
                preview = full_text[:200] + "..." if len(full_text) > 200 else full_text
                
                with st.expander(f"Section: {header}", expanded=True):
                    # Checkbox to enable/disable section
                    is_enabled = st.checkbox(
                        "Include in Summary", 
                        value=st.session_state.section_enabled.get(header, True),
                        key=f"enable_{header}"
                    )
                    st.session_state.section_enabled[header] = is_enabled
                    
                    if is_enabled:
                        st.caption(preview)
                        selected_files = st.multiselect(
                            f"Select resources for '{header}'",
                            options=resource_names,
                            key=f"link_{header}"
                        )
                        links[header] = selected_files
                    else:
                        st.caption("🚫 *Section excluded from summary*")

            st.divider()
            st.divider()
            if st.button("Generate Report", type="primary"):
                st.session_state.section_links = links
                
                # Filter only enabled sections
                final_plan = {
                    h: links[h] 
                    for h, enabled in st.session_state.section_enabled.items() 
                    if enabled and h in links
                }
                
                # Create a map of filename -> bytes for easy access
                # We need to seek(0) to ensure we read from the start if read before (though Streamlit usually handles this)
                resource_map = {f.name: f.getvalue() for f in uploaded_resources}
                
                st.write("### Generating Report...")
                progress_bar = st.progress(0)
                total_sections = len(final_plan)
                
                generated_report = {}
                
                # Prepare tasks
                tasks = []
                with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
                    future_to_header = {}
                    
                    for header, linked_files in final_plan.items():
                        # Get previous text
                        previous_text_parts = st.session_state.sections.get(header, [])
                        previous_text = "\n".join(previous_text_parts)
                        
                        # Get new PDF bytes
                        new_pdf_bytes_list = [resource_map[fname] for fname in linked_files if fname in resource_map]
                        
                        # Submit task
                        future = executor.submit(generate_section_summary, header, previous_text, new_pdf_bytes_list)
                        future_to_header[future] = header
                    
                    # Process results as they complete
                    for i, future in enumerate(concurrent.futures.as_completed(future_to_header)):
                        header = future_to_header[future]
                        try:
                            st.write(f"Completed: **{header}**")
                            new_section_content = future.result()
                            generated_report[header] = new_section_content
                        except Exception as e:
                            st.error(f"Error generating {header}: {e}")
                            generated_report[header] = f"Error: {e}"
                        
                        progress_bar.progress((i + 1) / total_sections)

                st.success("Report Generation Complete!")
                
                st.divider()
                st.header("Generated Report")
                
                full_report_text = ""
                for header, content in generated_report.items():
                    st.subheader(header)
                    st.write(content)
                    full_report_text += f"# {header}\n\n{content}\n\n"
                
                st.download_button(
                    label="Download Full Report",
                    data=full_report_text,
                    file_name="generated_report.md",
                    mime="text/markdown"
                )


                

