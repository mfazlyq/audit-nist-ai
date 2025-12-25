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
    pdf.cell(190, 10, "LAPORAN 12 GAP PRIORITAS UTAMA (NIST CSF 2.0)", ln=True, align='C')
    pdf.ln(10)
    pdf.set_font("Arial", '', 10)
    pdf.multi_cell(190, 7, summary_text)
    pdf.ln(5)
    with tempfile.NamedTemporaryFile(delete=False, suffix=".png") as tmp:
        tmp.write(plot_buf.getvalue()); pdf.image(tmp.name, x=25, y=pdf.get_y(), w=140) # Ukuran gambar di PDF disesuaikan
    pdf.add_page()
    for i in range(len(df)):
        pdf.set_font("Arial", 'B', 9)
        pdf.multi_cell(190, 7, f"Prioritas #{i+1} | [{df.iloc[i,0]}] ID: {df.iloc[i,1]}", border='TLR', fill=False)
        pdf.set_font("Arial", '', 8)
        pdf.multi_cell(190, 6, f"Situasi: {df.iloc[i,2]}", border='LR')
        pdf.multi_cell(190, 6, f"Saran: {df.iloc[i,3]}", border='BLR')
        pdf.ln(2)
    return pdf.output(dest='S').encode('latin-1')

# --- SIDEBAR ---
nist_file = st.sidebar.file_uploader("Upload Standar NIST (PDF)", type="pdf")
sop_file = st.sidebar.file_uploader("Upload SOP Kampus (PDF)", type="pdf")

if nist_file and sop_file:
    if st.button("🚀 Analisa 12 Gap Prioritas Utama"):
        with st.spinner("Mencari 12 celah keamanan paling kritis (Prioritas 1-12)..."):
            try:
                # Ingesti Dokumen
                with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as t1: t1.write(nist_file.read()); n_p = t1.name
                with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as t2: t2.write(sop_file.read()); s_p = t2.name
                
                docs = []
                for p in [n_p, s_p]: docs.extend(PyPDFLoader(p).load())
                splits = RecursiveCharacterTextSplitter(chunk_size=1200, chunk_overlap=200).split_documents(docs)
                vstore = Chroma.from_documents(documents=splits, embedding=HuggingFaceEmbeddings(model_name="sentence-transformers/all-MiniLM-L6-v2"))
                
                # Menggunakan model Llama 3.1 70B untuk ranking prioritas yang akurat
                llm = ChatGroq(model_name="llama-3.1-70b-versatile", temperature=0)
                
                pilar_nist = ["GOVERN", "IDENTIFY", "PROTECT", "DETECT", "RESPOND", "RECOVER"]
                
                # Mengambil konteks kolektif (Top 15 Chunks) untuk melihat celah lintas pilar
                relevant_docs = vstore.as_retriever(search_kwargs={"k": 15}).invoke("Cari celah keamanan paling kritis dalam SOP berdasarkan standar NIST CSF 2.0")
                context_text = "\n\n".join([d.page_content for d in relevant_docs])
                
                # PROMPT: Global Ranking 1-12 (Random Pilar berdasarkan urgensi)
                prompt = f"""
                TUGAS: Auditor Keamanan Senior. Analisis seluruh SOP dan temukan 12 GAP PALING KRITIS secara keseluruhan (Global Ranking).
                KONTEKS: {context_text}
                
                INSTRUKSI:
                1. Identifikasi 12 temuan paling berbahaya (prioritas utama) dari pilar NIST mana pun secara acak (berdasarkan urgensi).
                2. Urutkan dari Prioritas 1 (Paling Mendesak) sampai 12.
                3. Berikan pilar asal yang sesuai untuk setiap temuan.

                FORMAT OUTPUT (WAJIB 12 BARIS):
                PILAR | ID_KONTROL | [Situasi Kekurangan: max 15 kata] | [Saran Mitigasi: max 15 kata]
                
                Hanya berikan 12 baris data dengan pemisah '|'. Tanpa teks tambahan.
                """
                
                resp = llm.invoke(prompt).content
                all_results = []
                for line in resp.strip().split('\n'):
                    if "|" in line and len(line.split("|")) >= 4:
                        parts = [p.strip() for p in line.split("|")]
                        all_results.append(parts[:4])
                
                # Jeda stabilitas
                time.sleep(2)

                if all_results:
                    df = pd.DataFrame(all_results[:12], columns=["Fungsi", "ID", "Current Situation", "Action Plan"])
                    
                    st.success("✅ Berhasil Mengidentifikasi 12 Gap Prioritas Utama (Ranking 1-12)")
                    st.table(df)

                    # --- VISUALISASI SPIDER DIAGRAM (Ukuran Normal) ---
                    st.subheader("📊 NIST Compliance Gap Intensity Radar")
                    counts = df['Fungsi'].value_counts().reindex(pilar_nist, fill_value=0)
                    
                    labels = np.array(pilar_nist)
                    stats = counts.values

                    angles = np.linspace(0, 2*np.pi, len(labels), endpoint=False).tolist()
                    stats = np.concatenate((stats, [stats[0]]))
                    angles = np.concatenate((angles, [angles[0]]))

                    # Ukuran figsize diubah menjadi (6, 6) agar lebih normal
                    fig, ax = plt.subplots(figsize=(6, 6), subplot_kw=dict(polar=True))
                    ax.fill(angles, stats, color='red', alpha=0.3)
                    ax.plot(angles, stats, color='red', linewidth=1.5)
                    
                    ax.set_yticklabels([])
                    ax.set_xticks(angles[:-1])
                    ax.set_xticklabels(labels, size=9)
                    
                    st.pyplot(fig)
                    
                    buf = io.BytesIO()
                    plt.savefig(buf, format='png', bbox_inches='tight')

                    summary_txt = f"Audit Prioritas: 12 gap utama telah diidentifikasi. Pilar {counts.idxmax()} menunjukkan konsentrasi celah keamanan tertinggi."
                    st.info(summary_txt)
                    
                    st.sidebar.divider()
                    st.sidebar.download_button("📊 Excel", df.to_csv(index=False).encode('utf-8'), "Audit_Prioritas_12.csv")
                    st.sidebar.download_button("📄 PDF", create_pdf(df, summary_txt, buf), "Audit_Prioritas_12.pdf")
                else:
                    st.error("Gagal mendapatkan data. Silakan coba klik tombol audit kembali.")

            except Exception as e:
                st.error(f"Sistem: {e}")

else:
    st.info("👋 Selamat Datang! Silakan unggah kedua file PDF di sidebar kiri untuk mengaktifkan tombol audit.")

st.divider()
st.caption("Prototipe Sistem Audit Otomatis NIST CSF 2.0 - 2025")