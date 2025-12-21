import streamlit as st
import os
import tempfile
import pandas as pd
import io
import re
from langchain_community.document_loaders import PyPDFLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_community.vectorstores import Chroma
from langchain_groq import ChatGroq
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import RunnablePassthrough

# --- 1. KONFIGURASI API KEY ---
if "GROQ_API_KEY" in st.secrets:
    os.environ["GROQ_API_KEY"] = st.secrets["GROQ_API_KEY"]
else:
    os.environ["GROQ_API_KEY"] = "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"

st.set_page_config(page_title="AI Cyber-Auditor NIST CSF 2.0", layout="wide")
st.title("🛡️ AI Cyber-Auditor: NIST CSF 2.0 Compliance")

# --- 2. SIDEBAR ---
st.sidebar.header("📂 Data Audit")
nist_file = st.sidebar.file_uploader("Upload Standar NIST CSF 2.0 (PDF)", type="pdf")
sop_file = st.sidebar.file_uploader("Upload SOP IT Kampus (PDF)", type="pdf")

# --- 3. PROSES UTAMA ---
if nist_file and sop_file:
    if st.button("🚀 Jalankan Analisis Terstruktur"):
        with st.spinner("Menganalisis dan memetakan data ke format Excel NIST..."):
            try:
                # Ingestion
                with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp_nist:
                    tmp_nist.write(nist_file.getvalue()); nist_path = tmp_nist.name
                with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp_sop:
                    tmp_sop.write(sop_file.getvalue()); sop_path = tmp_sop.name

                loaders = [PyPDFLoader(nist_path), PyPDFLoader(sop_path)]
                docs = []
                for loader in loaders: docs.extend(loader.load())

                text_splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=150)
                splits = text_splitter.split_documents(docs)

                embeddings = HuggingFaceEmbeddings(model_name="sentence-transformers/all-MiniLM-L6-v2")
                vectorstore = Chroma.from_documents(documents=splits, embedding=embeddings)
                retriever = vectorstore.as_retriever(search_kwargs={"k": 3})

                llm = ChatGroq(model_name="llama-3.1-8b-instant", temperature=0)

                # PROMPT BARU: Meminta AI memberikan pemisah khusus (misal |) agar mudah dipisahkan ke kolom
                template = """
                Anda adalah Auditor Keamanan Siber Senior. Berikan analisis gap dalam format baris per baris.
                Gunakan pemisah " | " untuk setiap kolom.
                
                Format setiap baris harus:
                Kategori | Subkategori | Current Status | Action Plan
                
                Contoh:
                PROTECT | PR.AC-01 | Belum ada MFA | Implementasikan MFA di semua sistem utama
                
                Konteks: {context}
                Tugas: Temukan semua gap antara SOP dan NIST CSF 2.0. Berikan jawaban HANYA dalam format baris-baris tersebut.
                """
                prompt = ChatPromptTemplate.from_template(template)
                rag_chain = ({"context": retriever, "question": RunnablePassthrough()} | prompt | llm)
                
                response = rag_chain.invoke("Lakukan audit gap analysis")
                raw_text = response.content

                # --- 4. LOGIKA PARSING KE EXCEL ---
                rows = []
                for line in raw_text.strip().split('\n'):
                    if "|" in line:
                        parts = [p.strip() for p in line.split("|")]
                        if len(parts) >= 4:
                            rows.append(parts[:4])

                # Membuat DataFrame dengan kolom yang sesuai template NIST
                df = pd.DataFrame(rows, columns=[
                    "CSF Function/Category", 
                    "Subcategory ID", 
                    "Current Status (Current Profile)", 
                    "Action Plan (Target Profile)"
                ])

                # Tampilkan di Streamlit
                st.success("✅ Analisis Selesai!")
                st.table(df)

                # Export ke Excel
                output = io.BytesIO()
                with pd.ExcelWriter(output, engine='openpyxl') as writer:
                    df.to_excel(writer, index=False, sheet_name='NIST_Profile_Report')
                
                st.sidebar.divider()
                st.sidebar.download_button(
                    label="📥 Download NIST Profile (Excel)",
                    data=output.getvalue(),
                    file_name="NIST_CSF_Organizational_Profile.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                )

            except Exception as e:
                st.error(f"Error: {e}")