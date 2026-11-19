# NIST AI Audit Assistant

A Streamlit-based prototype that helps review campus cybersecurity policies and procedures against the NIST Cybersecurity Framework (CSF) by retrieving relevant PDF passages and using a large language model to draft prioritized findings.

> **Project status:** Research/prototype. This tool is decision support, not a certified audit system. Every finding and recommendation must be checked by a qualified human auditor.

## Overview

The application accepts two PDF documents:

1. A NIST reference document.
2. A campus SOP or policy document.

It extracts text from both documents, creates semantic chunks and embeddings, retrieves relevant passages, and asks an LLM to draft up to 12 prioritized gap findings. Results are presented in a table and a radar-style chart, with CSV and PDF export options.

## Features

- Upload NIST reference and campus SOP documents in PDF format.
- Extract PDF text and split it into overlapping chunks.
- Generate embeddings with **sentence-transformers/all-MiniLM-L6-v2**.
- Store and retrieve document chunks with **Chroma**.
- Use Groq-hosted LLM inference to draft prioritized findings.
- Group findings across the six NIST CSF functions: Govern, Identify, Protect, Detect, Respond, and Recover.
- Visualize the distribution of findings.
- Download findings as CSV and an audit summary as PDF.
- Cache completed analysis in the Streamlit session to avoid repeating work for the same input files.

## Workflow

~~~text
NIST PDF + Campus SOP PDF
          |
          v
     PDF extraction
          |
          v
  Text splitting / chunking
          |
          v
  Embedding + Chroma index
          |
          v
 Relevant passage retrieval
          |
          v
      Groq LLM analysis
          |
          v
 Parse and validate findings
          |
          v
 Table + chart + CSV/PDF report
~~~

## Technology stack

| Area | Technology |
|---|---|
| User interface | Streamlit |
| PDF extraction | PyPDF / LangChain PDF loader |
| Text processing | LangChain text splitters |
| Embeddings | Hugging Face Sentence Transformers |
| Vector store | Chroma |
| LLM integration | LangChain Groq |
| Data processing | pandas, NumPy |
| Visualization | Matplotlib |
| PDF report | FPDF |

## Getting started

### 1. Clone the repository

~~~bash
git clone https://github.com/mfazlyq/audit-nist-ai.git
cd audit-nist-ai
~~~

### 2. Create and activate a virtual environment

**Windows (PowerShell):**

~~~powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
~~~

**macOS / Linux:**

~~~bash
python -m venv .venv
source .venv/bin/activate
~~~

### 3. Install dependencies

~~~bash
python -m pip install --upgrade pip
pip install -r requirements.txt
~~~

### 4. Configure the Groq API key

The application reads **GROQ_API_KEY** from the environment or Streamlit secrets.

**Option A — Streamlit secrets (recommended for local use)**

Create **.streamlit/secrets.toml**:

~~~toml
GROQ_API_KEY = "your_groq_api_key"
~~~

**Option B — Environment variable**

PowerShell:

~~~powershell
$env:GROQ_API_KEY = "your_groq_api_key"
~~~

macOS / Linux:

~~~bash
export GROQ_API_KEY="your_groq_api_key"
~~~

Never commit API keys, **.env** files, or **.streamlit/secrets.toml** to Git.

### 5. Run the application

~~~bash
streamlit run app.py
~~~

Streamlit will print a local URL in the terminal. Open that URL in your browser.

## How to use

1. Start the application.
2. Upload the NIST reference PDF in the sidebar.
3. Upload the campus SOP or policy PDF.
4. Select **Analyze 12 Priority Gaps**.
5. Review the findings, function distribution, and recommendations.
6. Export the results as CSV or PDF.

The exact labels in the interface may be in Indonesian.

## Repository structure

~~~text
audit-nist-ai/
├── app.py
├── requirements.txt
├── README.md
└── .gitignore
~~~

## Important limitations and responsible use

- **Validate every finding.** LLM-generated findings may be incomplete, incorrectly ranked, or mapped to an incorrect control identifier.
- **Review source evidence.** Treat the generated output as an initial assessment, not proof of compliance or non-compliance.
- **Protect sensitive documents.** Retrieved document passages are included in prompts sent to the configured Groq service. Do not upload confidential, personal, or restricted institutional documents unless you have the required authorization and have reviewed the provider's data-handling terms.
- **Check framework references.** Confirm control identifiers and interpretations against the official NIST publication used by your institution.
- **No compliance certification.** The tool does not replace a formal risk assessment, audit process, or professional judgment.

## Author

**M. Fazly Qusyairy**

GitHub: [@mfazlyq](https://github.com/mfazlyq)

---

Built as a prototype for exploring AI-assisted cybersecurity governance and NIST CSF gap analysis in higher-education environments.
