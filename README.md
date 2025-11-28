# **auto_report_gen**

**auto_report_gen** is a tool designed to streamline and partially automate the redaction of annual reports.
It assists in reusing last year’s report structure, integrating updated project information, and generating high-quality section drafts using GPT-based models.

---

## **✨ Overview**

Writing annual reports each year often involves reusing the same structure, updating project contributions, and ensuring consistency in tone and length.
**auto_report_gen** automates most of this workflow by:

* Parsing last year’s report into structured sections
* Allowing you to map new project reports to these sections
* Automatically generating updated text through a customized prompt pipeline powered by the ChatGPT API (model: **GPT-5 Mini**)
* Running all section generations **concurrently** for speed

---

## **🚀 Features**

### **1. Upload Last Year’s Report**

* The report is automatically parsed into the major relevant sections.
* These sections act as templates for the updated content.

### **2. Upload Project Reports**

* Add all the project reports that should contribute to this year’s annual report.

### **3. Section–Project Mapping**

* Select which project reports feed into which sections.
* Multiple projects can be linked to the same section.

### **4. Add Additional Comments**

* Provide clarifications, priorities, or stylistic notes.
* Comments guide the generation of each section’s text.

### **5. Custom Prompt Generation**

For every section, a tailored prompt is assembled containing:

* The text from last year's corresponding section
* The selected project report(s)
* Your additional comments
* Internal guidelines ensuring consistency in **tone**, **format**, and **length**

### **6. Automatic Text Generation**

* All section prompts are sent to the ChatGPT API **in parallel**.
* Each section is generated independently using **GPT-5 Mini**.
* The resulting texts form a complete draft of the updated annual report.

---

## **🧩 Pipeline Summary**

```
Last Year's Report
        ↓ (parsed)
  Structured Sections
        ↓
 Upload Project Reports
        ↓
Map Projects → Sections
        ↓
 Add Comments & Guidelines
        ↓
  Custom Prompt Creation
        ↓
Parallel Generation via GPT-5 Mini
        ↓
   Updated Annual Report Draft
```

---

## **🛠️ Requirements**

* Python ≥ 3.9
* Access to the OpenAI/ChatGPT API
* Dependencies listed in `requirements.txt`

---

## **📦 Installation**

```bash
git clone https://github.com/your-username/auto_report_gen.git
cd auto_report_gen
pip install -r requirements.txt
```

---

## **▶️ Usage**

1. Launch the interface or script depending on your setup.
2. Upload last year’s report.
3. Upload project reports.
4. Map each project report to the appropriate section(s).
5. Add optional comments.
6. Generate the report text.
7. Retrieve the final section drafts from the output directory or UI.

---

## **🤖 Model & API**

* Uses **GPT-5 Mini** for text generation.
* Sections are generated concurrently for optimal performance.

---

## **📄 License**

Specify your license here (MIT, Apache 2.0, GPL, etc.).

---

## **🙌 Contributions**

Pull requests and suggestions are welcome!
Feel free to open an issue to report bugs or request features.
