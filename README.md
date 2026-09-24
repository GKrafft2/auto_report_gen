# **auto_report_gen**

**auto_report_gen** is a tool designed to streamline and partially automate the redaction of annual reports. It assists in reusing last year’s report structure, integrating updated project information, and generating high-quality section drafts using GPT-based models.

---

## **✨ Overview**

Writing annual reports each year often involves reusing the same structure, updating project contributions, and ensuring consistency in tone and length. **auto_report_gen** automates most of this workflow by:

*   **Parsing last year’s report** into structured sections using **Docling**.
*   **Allowing you to map new project reports** (PDFs) to these sections via a **Streamlit** interface.
*   **Automatically generating updated text** through a customized prompt pipeline powered by the ChatGPT API (model: **GPT-5 Mini**).
*   **Running all section generations concurrently** for speed.

---

## **🚀 Features**

### **1. Interactive Frontend (Streamlit)**
A user-friendly web interface guides you through the entire process, from uploading files to downloading the final report.

### **2. Upload Last Year’s Report**
*   Upload your previous year's PDF.
*   The system automatically parses it into major sections using **Docling**'s advanced document understanding.

### **3. Upload & Link Resources**
*   Upload multiple new resource PDFs (project reports, updates, etc.).
*   Interactively link specific resources to specific sections of the report.
*   **Select/Unselect All** functionality for quick configuration.

### **4. Custom Instructions**
*   Add manual comments or instructions for specific sections (e.g., "Emphasize the new partnership", "Keep this brief").
*   These comments are directly injected into the generation prompt.

### **5. Smart Generation Pipeline**
For every section, a tailored prompt is assembled containing:
*   The text from last year's corresponding section (for style and context).
*   The text from the linked new resources.
*   Your manual instructions.
*   Internal guidelines ensuring consistency in **tone**, **format**, and **length**.

### **6. Parallel Execution**
*   All section prompts are sent to the ChatGPT API **in parallel**.
*   Uses **GPT-5 Mini** (or configured model) for high-quality text generation.

---

## **🛠️ Requirements**

*   Python ≥ 3.13
*   Access to the OpenAI/ChatGPT API (API Key required)
*   **uv** (recommended) or pip for dependency management

---

## **📦 Installation**

This project uses `uv` for fast dependency management, but can also be installed via standard `pip`.

### **Option 1: Using uv (Recommended)**

1.  **Install uv** (if not already installed):
    ```bash
    pip install uv
    ```

2.  **Clone the repository**:
    ```bash
    git clone https://github.com/GKrafft2/auto_report_gen.git
    cd auto_report_gen
    ```

3.  **Sync dependencies**:
    ```bash
    uv sync
    ```

### **Option 2: Using pip**

1.  **Clone the repository**:
    ```bash
    git clone https://github.com/GKrafft2/auto_report_gen.git
    cd auto_report_gen
    ```

2.  **Install dependencies**:
    ```bash
    pip install .
    ```

---

## **▶️ Usage**

1.  **Set up your API Key**:
    Create a `.env` file in the root directory and add your OpenAI API key:
    ```env
    OPENAI_API_KEY=sk-...
    ```

2.  **Run the Streamlit App**:
    ```bash
    # If using uv
    uv run streamlit run front_end/main_frontend.py

    # If using standard pip/venv
    streamlit run front_end/main_frontend.py
    ```

3.  **Workflow**:
    *   **Step 1**: Upload Last Year's PDF and click "Parse Report".
    *   **Step 2**: Upload New Resource PDFs.
    *   **Step 3**: Expand sections to:
        *   Enable/Disable them.
        *   Link specific resource files.
        *   Add manual comments.
    *   **Step 4**: Click "Generate Report".
    *   **Step 5**: Download the final Markdown report.

---

## **🤖 Model & API**

*   **Models**: Defaults to `gpt-5-mini` and `gpt-5-nano` (ensure your API key has access to these models).
*   **Docling**: Used for robust PDF parsing and chunking.

---

## **📄 License**

TBD

---

## **🙌 Contributions**

Pull requests and suggestions are welcome! Feel free to open an issue to report bugs or request features.
