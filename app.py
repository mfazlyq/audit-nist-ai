import streamlit as st
import os
import tempfile
import pandas as pd
import io
import time
import numpy as np  # Tambahan untuk Spider Diagram
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
elif "GROQ_API_KEY" in os.environ:
    pass  # sudah diset dari environment
else:
    st.error("❌ GROQ_API_KEY belum diset.")
    st.info("Silakan set API Key melalui Streamlit Secrets atau environment variable.")
    st.stop()

st.set_page_config(page_title="Expert NIST Auditor Pro", layout="wide")
st.title("🛡️Prototipe Sistem Audit Keamanan Siber Otomatis berbasis Web")

# --- FUNGSI PDF ---
def create_pdf(df, summary_text, plot_buf):
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", 'B', 16)
    pdf.cell(190, 10, "LAPORAN AUDIT NIST CSF 2.0 (12 GAP PRIORITAS)", ln=True, align='C')
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
    if st.button("🚀 Memulai Audit Analitis (12 Gap Prioritas)"):
        with st.spinner("Menganalisis 12 gap prioritas pilar demi pilar..."):
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
                    
                    # PROMPT DIUBAH UNTUK MENCARI 2 GAP PRIORITAS PER PILAR (TOTAL 12)
                    prompt = f"""
                    TUGAS: Auditor Keamanan Ahli. Identifikasi 2 temuan GAP PALING KRITIS untuk pilar: {nama}.
                    KONTEKS: {context_text}
                    
                    INSTRUKSI:
                    1. 'Situasi': Jelaskan 2 kekurangan SOP yang paling mendesak (masing-masing sekitar 15 kata).
                    2. 'Saran': Langkah perbaikan sesuai NIST (masing-masing sekitar 15 kata).

                    FORMAT OUTPUT (WAJIB 2 BARIS):
                    {nama} | {prefix}.XX.01 | [Situasi 1] | [Saran 1]
                    {nama} | {prefix}.XX.02 | [Situasi 2] | [Saran 2]
                    
                    Hanya berikan baris yang mengandung karakter '|'. Dilarang memberikan teks basa-basi.
                    """
                    
                    try:
                        resp = llm.invoke(prompt).content
                        for line in resp.strip().split('\n'):
                            if "|" in line and len(line.split("|")) >= 4:
                                parts = [p.strip() for p in line.split("|")]
                                all_results.append(parts[:4])
                    except Exception:
                        pass
                    
                    # TPM ADJUSTMENT: 6 detik untuk stabilitas
                    time.sleep(6) 
                    progress_bar.progress((idx + 1) / len(pilar_nist))

                if all_results:
                    df = pd.DataFrame(all_results, columns=["Fungsi", "ID", "Current Situation", "Action Plan"])
                    df = df.head(12) # Memastikan hanya 12 gap prioritas

                    st.success(f"✅ Audit Selesai: {len(df)} Gap Prioritas Utama Teridentifikasi.")
                    st.table(df)

                    # --- VISUALISASI SPIDER DIAGRAM ---
                    st.subheader("📊 NIST CSF 2.0 Compliance Radar")
                    counts = df['Fungsi'].value_counts().reindex([p[0] for p in pilar_nist], fill_value=0)
                    
                    labels = np.array([p[0] for p in pilar_nist])
                    stats = counts.values

                    angles = np.linspace(0, 2*np.pi, len(labels), endpoint=False).tolist()
                    
                    # Menutup loop radar
                    stats = np.concatenate((stats, [stats[0]]))
                    angles = np.concatenate((angles, [angles[0]]))

                    fig, ax = plt.subplots(figsize=(8, 8), subplot_kw=dict(polar=True))
                    ax.fill(angles, stats, color='#1f77b4', alpha=0.25)
                    ax.plot(angles, stats, color='#1f77b4', linewidth=2)
                    
                    ax.set_yticklabels([])
                    ax.set_xticks(angles[:-1])
                    ax.set_xticklabels(labels)
                    
                    st.pyplot(fig)
                    
                    buf = io.BytesIO()
                    plt.savefig(buf, format='png')

                    summary_txt = f"Total 12 gap prioritas ditemukan. Fokus utama perbaikan pada pilar {counts.idxmax()}."
                    st.info(summary_txt)
                    
                    st.sidebar.divider()
                    st.sidebar.download_button("📊 Excel", df.to_csv(index=False).encode('utf-8'), "Audit_Priority_Report.csv")
                    st.sidebar.download_button("📄 PDF", create_pdf(df, summary_txt, buf), "Audit_Priority_Report.pdf")
                else:
                    st.error("Gagal mendapatkan data. Server Groq sedang sibuk, silakan tunggu 1 menit dan coba lagi.")

            except Exception as e:
                st.error(f"Sistem: {e}")

else:
    st.info("👋 Selamat Datang! Silakan unggah kedua file PDF di sidebar kiri untuk mengaktifkan tombol audit.")

st.divider()
st.caption("Prototipe Sistem Audit Otomatis NIST CSF 2.0 - 2025")