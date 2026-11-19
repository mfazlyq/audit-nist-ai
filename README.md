# NIST AI Audit Assistant

![Python tests](https://github.com/mfazlyq/audit-nist-ai/actions/workflows/tests.yml/badge.svg)
![Python](https://img.shields.io/badge/Python-3.11+-3776AB?logo=python&logoColor=white)
![Status](https://img.shields.io/badge/Status-Research%20Prototype-orange)

A Streamlit-based research prototype that explores AI-assisted review of campus cybersecurity policies and procedures against the NIST Cybersecurity Framework (CSF).

> **Project status:** Research prototype and decision-support tool. It is not a certified audit system. Every finding and recommendation must be verified by a qualified human auditor.

## Overview

The application accepts a NIST reference PDF and a campus SOP or policy PDF. It extracts text, creates semantic chunks and embeddings, retrieves relevant passages, and asks a language model to draft prioritized gap findings. Results are presented in a table and a radar-style chart, with CSV and PDF export options.

## Features

- Upload NIST reference and campus SOP documents in PDF format.
- Extract PDF text and split it into overlapping chunks.
- Generate embeddings with **sentence-transformers/all-MiniLM-L6-v2**.
- Store and retrieve document chunks with **Chroma**.
- Use Groq-hosted LLM inference to draft prioritized findings.
- Validate returned NIST CSF function names and control-ID formats before displaying findings.
- Visualize the distribution of findings across the six NIST CSF functions.
- Download findings as CSV and an audit summary as PDF.
- Cache completed analysis in the Streamlit session for the same input files.

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
| Unit tests / CI | Python unittest, GitHub Actions |

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

**Option A — Streamlit secrets**

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

The [.env.example](.env.example) file is a reference template only; the application does not automatically load a .env file. Never commit real API keys, .env files, or .streamlit/secrets.toml.

### 5. Run the application

~~~bash
streamlit run app.py
~~~

Streamlit will print a local URL in the terminal. Open that URL in your browser.

## How to use

1. Start the application.
2. Upload the NIST reference PDF in the sidebar.
3. Upload the campus SOP or policy PDF.
4. Select **Analisa 12 Gap Prioritas Utama**.
5. Review the findings, function distribution, and recommendations.
6. Export the results as CSV or PDF.

The user interface currently uses Indonesian labels.

## Run tests

The parser unit tests use Python's standard library and do not require the full application dependencies:

~~~bash
python -m unittest discover -s tests -v
~~~

A GitHub Actions workflow runs these tests on pushes to main and pull requests targeting main.

## Repository structure

~~~text
audit-nist-ai/
├── .github/
│   └── workflows/
│       └── tests.yml
├── docs/
│   ├── ARCHITECTURE.md
│   ├── GITHUB_PROFILE_README.md
│   └── SECURITY.md
├── tests/
│   └── test_audit_utils.py
├── .env.example
├── .gitignore
├── app.py
├── audit_utils.py
├── README.md
└── requirements.txt
~~~

## Documentation

- [Architecture and implementation notes](docs/ARCHITECTURE.md)
- [Security and data-handling notes](docs/SECURITY.md)
- [Prepared GitHub profile README](docs/GITHUB_PROFILE_README.md)

## Important limitations and responsible use

- **Validate every finding.** LLM-generated findings may be incomplete, incorrectly ranked, or mapped to an incorrect control identifier.
- **Review source evidence.** The parser checks the function name and control-ID format, but it cannot prove that a finding is supported by the uploaded evidence.
- **Retrieval is not exhaustive.** A broad retrieval query does not guarantee complete coverage of every NIST CSF outcome.
- **Ranking is provisional.** The current ordering is generated by the language model and is not a formally calibrated risk score.
- **Protect sensitive documents.** Retrieved document passages are included in prompts sent to the configured Groq service. Do not upload confidential, personal, or restricted institutional documents unless you have the required authorization and have reviewed the provider's current data-handling terms.
- **No compliance certification.** The tool does not replace a formal risk assessment, audit process, or professional judgment.

## Author

**M. Fazly Qusyairy**

GitHub: [@mfazlyq](https://github.com/mfazlyq)

---

Built as a prototype for exploring AI-assisted cybersecurity governance and NIST CSF gap analysis in higher-education environments.
