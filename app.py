import streamlit as st
import os
import tempfile
import pandas as pd
import io
import time
import hashlib # Untuk logika deteksi revisi file
import numpy as np
import matplotlib.pyplot as plt
from fpdf import FPDF 
from langchain_community.document_loaders import PyPDFLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_community.vectorstores import Chroma
from langchain_groq import ChatGroq

# --- 1. SETUP API & PAGE ---
if "GROQ_API_KEY" in st.secrets:
    os.environ["GROQ_API_KEY"] = st.secrets["GROQ_API_KEY"]
elif "GROQ_API_KEY" in os.environ:
    pass  
else:
    st.error("❌ API Key tidak ditemukan.")
    st.stop()

st.set_page_config(page_title="Expert NIST Auditor Pro", layout="wide")
st.title("🛡️ Prototipe Sistem Audit Keamanan Siber Otomatis berbasis Web")

# --- FUNGSI HASH (UNTUK DETEKSI REVISI) ---
def get_file_hash(file_bytes):
    return hashlib.sha256(file_bytes).hexdigest()

# --- FUNGSI PDF ---
def create_pdf(df, summary_text, plot_buf):
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", 'B', 14)
    pdf.cell(190, 10, "LAPORAN 12 GAP PRIORITAS UTAMA (NIST CSF 2.0)", ln=True, align='C')
    pdf.ln(5)
    pdf.set_font("Arial", '', 10)
    pdf.multi_cell(190, 7, summary_text)
    pdf.ln(5)
    with tempfile.NamedTemporaryFile(delete=False, suffix=".png") as tmp:
        tmp.write(plot_buf.getvalue())
        pdf.image(tmp.name, x=45, y=pdf.get_y(), w=110)
    pdf.add_page()
    for i in range(len(df)):
        pdf.set_font("Arial", 'B', 9)
        pdf.multi_cell(190, 7, f"Prioritas #{i+1} | [{df.iloc[i,0]}] ID: {df.iloc[i,1]}", border='TLR')
        pdf.set_font("Arial", '', 8)
        pdf.multi_cell(190, 6, f"Situasi: {df.iloc[i,2]}", border='LR')
        pdf.multi_cell(190, 6, f"Saran: {df.iloc[i,3]}", border='BLR')
        pdf.ln(2)
    return pdf.output(dest='S').encode('latin-1')

# --- SIDEBAR ---
nist_file = st.sidebar.file_uploader("Upload Standar NIST (PDF)", type="pdf")
sop_file = st.sidebar.file_uploader("Upload SOP Kampus (PDF)", type="pdf")

# Inisialisasi Cache di Session State
if "audit_cache" not in st.session_state:
    st.session_state.audit_cache = {}

if nist_file and sop_file:
    # Ambil isi file untuk hashing
    sop_bytes = sop_file.getvalue()
    file_id = get_file_hash(sop_bytes)
    
    if st.button("🚀 Analisa 12 Gap Prioritas Utama"):
        # Cek apakah file sudah pernah diaudit dan belum berubah
        if file_id in st.session_state.audit_cache:
            st.info("ℹ️ File yang sama terdeteksi. Mengambil hasil audit dari memori sistem...")
            # Hasil akan ditampilkan dari cache di bawah
        else:
            with st.spinner("Mengevaluasi celah keamanan berdasarkan ID NIST asli (Analisis Baru)..."):
                try:
                    with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as t1: t1.write(nist_file.read()); n_p = t1.name
                    with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as t2: t2.write(sop_bytes); s_p = t2.name
                    
                    docs = []
                    for p in [n_p, s_p]: docs.extend(PyPDFLoader(p).load())
                    splits = RecursiveCharacterTextSplitter(chunk_size=1200, chunk_overlap=200).split_documents(docs)
                    vstore = Chroma.from_documents(documents=splits, embedding=HuggingFaceEmbeddings(model_name="sentence-transformers/all-MiniLM-L6-v2"))
                    
                    # Menggunakan model stabil terbaru
                    llm = ChatGroq(model_name="llama-3.3-70b-versatile", temperature=0)
                    
                    pilar_nist = ["GOVERN", "IDENTIFY", "PROTECT", "DETECT", "RESPOND", "RECOVER"]
                    
                    relevant_docs = vstore.as_retriever(search_kwargs={"k": 15}).invoke("Cari celah keamanan paling kritis dalam SOP berdasarkan standar NIST CSF 2.0")
                    context_text = "\n\n".join([d.page_content for d in relevant_docs])
                    
                    # --- PROMPT REVISI ANDA ---
                    prompt = f"""
                    TUGAS: Auditor Keamanan Senior. Temukan 12 GAP PALING KRITIS secara keseluruhan (Prioritas 1-12).
                    KONTEKS: {context_text}
                    
                    INSTRUKSI KHUSUS:
                    1. Gunakan ID Sub-kategori ASLI dari NIST CSF 2.0 (Contoh: GV.OC-01, ID.AM-01, PR.AA-01, dsb).
                    2. JANGAN MENGARANG ID. Cari ID yang paling relevan dengan celah keamanan yang ditemukan di SOP.
                    3. Identifikasi 12 temuan paling berbahaya tanpa membagi rata per pilar.
                    4. PILAR wajib salah satu dari: GOVERN, IDENTIFY, PROTECT, DETECT, RESPOND, RECOVER.
                    5. SITUASI: Jelaskan kekurangan SOP secara mendetail (WAJIB 10-15 kata).
                    6. SARAN: Berikan langkah mitigasi konkret (WAJIB 10-15 kata).

                    FORMAT OUTPUT (WAJIB 12 BARIS):
                    PILAR | ID_KONTROL | Situasi | Saran
                    
                    Contoh baris benar:
                    PROTECT | PR.AC-01 | SOP belum mengatur kebijakan akses kontrol fisik pada ruang server utama kampus. | Segera susun kebijakan akses fisik dan pasang perangkat autentikasi biometrik di ruang server.
                    """
                    
                    resp = llm.invoke(prompt).content
                    all_results = []
                    for line in resp.strip().split('\n'):
                        if "|" in line and len(line.split("|")) >= 4:
                            parts = [p.strip() for p in line.split("|")]
                            pilar_raw = parts[0].upper()
                            matched_pilar = next((p for p in pilar_nist if p in pilar_raw), None)
                            if matched_pilar:
                                all_results.append([matched_pilar, parts[1], parts[2], parts[3]])
                    
                    # Simpan ke cache
                    if all_results:
                        st.session_state.audit_cache[file_id] = all_results
                except Exception as e:
                    st.error(f"Terjadi kesalahan: {e}")

    # --- LOGIKA TAMPILAN PERSISTEN ---
    if file_id in st.session_state.audit_cache:
        current_data = st.session_state.audit_cache[file_id]
        df = pd.DataFrame(current_data[:12], columns=["Fungsi", "ID", "Current Situation", "Action Plan"])
        
        st.success(f"✅ Hasil Analisis 12 Gap Prioritas Utama")
        st.table(df)

        # --- VISUALISASI SPIDER DIAGRAM ---
        st.subheader("📊 NIST Compliance Gap Intensity Radar")
        pilar_nist_labels = ["GOVERN", "IDENTIFY", "PROTECT", "DETECT", "RESPOND", "RECOVER"]
        counts = df['Fungsi'].value_counts().reindex(pilar_nist_labels, fill_value=0)
        
        labels = np.array(pilar_nist_labels)
        stats = counts.values
        angles = np.linspace(0, 2*np.pi, len(labels), endpoint=False).tolist()
        stats = np.concatenate((stats, [stats[0]]))
        angles = np.concatenate((angles, [angles[0]]))

        fig, ax = plt.subplots(figsize=(5, 5), subplot_kw=dict(polar=True))
        ax.fill(angles, stats, color='red', alpha=0.3)
        ax.plot(angles, stats, color='red', linewidth=1.5, marker='o', markersize=4)
        ax.set_xticks(angles[:-1])
        ax.set_xticklabels(labels, size=8)
        
        max_val = int(stats.max()) if stats.max() > 0 else 1
        ax.set_yticks(range(0, max_val + 1))
        ax.set_yticklabels([str(i) for i in range(0, max_val + 1)], size=7)

        st.pyplot(fig)
        
        buf = io.BytesIO()
        plt.savefig(buf, format='png', bbox_inches='tight')

        summary_txt = f"Audit Prioritas selesai. Konsentrasi gap tertinggi ditemukan pada pilar {counts.idxmax()}."
        st.info(summary_txt)
        
        st.sidebar.divider()
        st.sidebar.download_button("📊 Excel", df.to_csv(index=False).encode('utf-8'), "Audit_Prioritas.csv")
        st.sidebar.download_button("📄 PDF", create_pdf(df, summary_txt, buf), "Audit_Prioritas.pdf")
else:
    st.info("👋 Silakan unggah file PDF untuk memulai audit.")

st.divider()
st.caption("Prototipe Sistem Audit Otomatis NIST CSF 2.0 - 2025")