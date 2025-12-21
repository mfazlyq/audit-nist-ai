import streamlit as st
import os
import tempfile
import pandas as pd
import io
import time
import matplotlib.pyplot as plt
from fpdf import FPDF 
from langchain_community.document_loaders import PyPDFLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_community.vectorstores import Chroma
from langchain_groq import ChatGroq
from langchain_core.prompts import ChatPromptTemplate

# --- 1. SETUP API & PAGE ---
if "GROQ_API_KEY" in st.secrets:
    os.environ["GROQ_API_KEY"] = st.secrets["GROQ_API_KEY"]
else:
    os.environ["GROQ_API_KEY"] = "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"

st.set_page_config(page_title="Expert NIST Auditor Pro", layout="wide")
st.title("🛡️ Expert AI Auditor: NIST CSF 2.0 (Stable & Detailed)")

# --- FUNGSI PDF ---
def create_pdf(df, summary_text, plot_buf):
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", 'B', 16)
    pdf.cell(190, 10, "LAPORAN AUDIT NIST CSF 2.0", ln=True, align='C')
    pdf.ln(10)
    pdf.set_font("Arial", '', 10)
    pdf.multi_cell(190, 7, summary_text)
    pdf.ln(5)
    with tempfile.NamedTemporaryFile(delete=False, suffix=".png") as tmp:
        tmp.write(plot_buf.getvalue()); pdf.image(tmp.name, x=15, y=pdf.get_y(), w=170)
    pdf.add_page()
    for i in range(len(df)):
        pdf.set_font("Arial", 'B', 9)
        pdf.multi_cell(190, 7, f"[{df.iloc[i,0]}] ID: {df.iloc[i,1]}", border='TLR', fill=False)
        pdf.set_font("Arial", '', 8)
        pdf.multi_cell(190, 6, f"Situasi: {df.iloc[i,2]}", border='LR')
        pdf.multi_cell(190, 6, f"Saran: {df.iloc[i,3]}", border='BLR')
        pdf.ln(2)
    return pdf.output(dest='S').encode('latin-1')

# --- SIDEBAR ---
nist_file = st.sidebar.file_uploader("Upload Standar NIST (PDF)", type="pdf")
sop_file = st.sidebar.file_uploader("Upload SOP Kampus (PDF)", type="pdf")

if nist_file and sop_file:
    if st.button("🚀 Memulai Audit Analitis "):
        with st.spinner("Menganalisis pilar demi pilar (Estimasi 30-45 detik)..."):
            try:
                # Ingesti Dokumen
                with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as t1: t1.write(nist_file.read()); n_p = t1.name
                with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as t2: t2.write(sop_file.read()); s_p = t2.name
                
                docs = []
                for p in [n_p, s_p]: docs.extend(PyPDFLoader(p).load())
                splits = RecursiveCharacterTextSplitter(chunk_size=1200, chunk_overlap=200).split_documents(docs)
                vstore = Chroma.from_documents(documents=splits, embedding=HuggingFaceEmbeddings(model_name="sentence-transformers/all-MiniLM-L6-v2"))
                
                llm = ChatGroq(model_name="llama-3.1-8b-instant", temperature=0)
                
                pilar_nist = [
                    ("GOVERN", "GV", "Tata kelola dan strategi."),
                    ("IDENTIFY", "ID", "Aset dan risiko."),
                    ("PROTECT", "PR", "Akses dan data."),
                    ("DETECT", "DE", "Deteksi kejadian."),
                    ("RESPOND", "RS", "Respon insiden."),
                    ("RECOVER", "RC", "Pemulihan.")
                ]
                
                all_results = []
                progress_bar = st.progress(0)
                
                for idx, (nama, prefix, desc) in enumerate(pilar_nist):
                    # Ambil konteks spesifik
                    relevant_docs = vstore.as_retriever(search_kwargs={"k": 4}).invoke(f"Audit NIST {nama}")
                    context_text = "\n\n".join([d.page_content for d in relevant_docs])
                    
                    prompt = f"""
                    TUGAS: Auditor NIST CSF 2.0. Berikan 1 temuan gap pilar: {nama}.
                    KONTEKS: {context_text}
                    
                    INSTRUKSI NARASI:
                    1. 'Situasi': Jelaskan kekurangan SOP (sekitar 15 kata).
                    2. 'Saran': Langkah perbaikan NIST (sekitar 15 kata).

                    FORMAT OUTPUT (WAJIB):
                    {nama} | {prefix}.XX-01 | [Situasi] | [Saran]
                    
                    Hanya berikan baris yang mengandung karakter '|'. Dilarang memberikan teks basa-basi.
                    """
                    
                    try:
                        resp = llm.invoke(prompt).content
                        # Logika Parsing Filter (Hanya ambil baris yang punya '|')
                        for line in resp.strip().split('\n'):
                            if "|" in line and len(line.split("|")) >= 4:
                                parts = [p.strip() for p in line.split("|")]
                                all_results.append(parts[:4])
                    except Exception:
                        pass
                    
                    # JEDA 4 DETIK (Sangat Penting untuk Akun Gratis)
                    time.sleep(4) 
                    progress_bar.progress((idx + 1) / len(pilar_nist))

                if all_results:
                    df = pd.DataFrame(all_results, columns=["Fungsi", "ID", "Current Situation", "Action Plan"])
                    df = df.drop_duplicates(subset=['ID'])

                    st.success(f"✅ Audit Selesai: {len(df)} Temuan Teridentifikasi.")
                    st.table(df)

                    # Visualisasi
                    counts = df['Fungsi'].value_counts().reindex([p[0] for p in pilar_nist], fill_value=0)
                    fig, ax = plt.subplots(figsize=(10, 4))
                    counts.plot(kind='bar', ax=ax, color='#1f77b4')
                    plt.xticks(rotation=0)
                    st.pyplot(fig)
                    
                    buf = io.BytesIO()
                    plt.savefig(buf, format='png')

                    summary_txt = f"Total {len(df)} gap ditemukan. Fokus utama pada pilar {counts.idxmax()}."
                    st.info(summary_txt)
                    
                    st.sidebar.divider()
                    st.sidebar.download_button("📊 Excel", df.to_csv(index=False).encode('utf-8'), "Audit_Report.csv")
                    st.sidebar.download_button("📄 PDF", create_pdf(df, summary_txt, buf), "Audit_Report.pdf")
                else:
                    st.error("Gagal mendapatkan data. Server Groq sedang sibuk, silakan tunggu 1 menit dan coba lagi.")

            except Exception as e:
                st.error(f"Sistem: {e}")

                else:
    st.warning("⚠️ Silakan upload file PDF di sidebar untuk memulai.")

st.divider()
st.caption("Penelitian Hibah Dosen Pemula 2024 - AI for Cybersecurity Compliance")