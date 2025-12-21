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

# --- 1. KONFIGURASI API & PAGE ---
if "GROQ_API_KEY" in st.secrets:
    os.environ["GROQ_API_KEY"] = st.secrets["GROQ_API_KEY"]
else:
    os.environ["GROQ_API_KEY"] = "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"

st.set_page_config(page_title="Expert NIST Auditor Pro", layout="wide")
st.title("🛡️ Expert AI Auditor: NIST CSF 2.0 (Sequential Mode)")

# --- 2. FUNGSI GENERATE PDF ---
def create_pdf(df, summary_text, plot_buf):
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", 'B', 16)
    pdf.cell(190, 10, "LAPORAN AUDIT TATA KELOLA NIST CSF 2.0", ln=True, align='C')
    pdf.ln(10)
    
    pdf.set_font("Arial", 'B', 12)
    pdf.cell(100, 10, "1. Ringkasan Eksekutif", ln=True)
    pdf.set_font("Arial", '', 10)
    pdf.multi_cell(190, 7, summary_text.replace("**", ""))
    pdf.ln(5)
    
    # Masukkan Grafik
    with tempfile.NamedTemporaryFile(delete=False, suffix=".png") as tmp_img:
        tmp_img.write(plot_buf.getvalue())
        pdf.image(tmp_img.name, x=15, y=pdf.get_y(), w=170)
    
    # Masukkan Tabel (Halaman Baru)
    pdf.add_page()
    pdf.set_font("Arial", 'B', 11)
    pdf.cell(100, 10, "2. Detail Temuan Per Pilar", ln=True)
    pdf.set_font("Arial", '', 8)
    
    for i in range(len(df)):
        pdf.set_font("Arial", 'B', 8)
        pdf.multi_cell(190, 7, f"[{df.iloc[i,0]}] ID: {df.iloc[i,1]}", border='TLR', fill=False)
        pdf.set_font("Arial", '', 8)
        pdf.multi_cell(190, 7, f"Situasi: {df.iloc[i,2]}", border='LR')
        pdf.multi_cell(190, 7, f"Saran: {df.iloc[i,3]}", border='BLR')
        pdf.ln(2)
        
    return pdf.output(dest='S').encode('latin-1')

# --- 3. SIDEBAR ---
st.sidebar.header("📂 Dokumen Sumber")
nist_file = st.sidebar.file_uploader("Upload Standar NIST (PDF)", type="pdf")
sop_file = st.sidebar.file_uploader("Upload SOP Kampus (PDF)", type="pdf")

# --- 4. LOGIKA UTAMA ---
if nist_file and sop_file:
    if st.button("🚀 Jalankan Audit Mendalam (Sekuensial)"):
        with st.spinner("Memulai proses audit pilar demi pilar..."):
            try:
                # Proses Ingesti
                with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as t1: t1.write(nist_file.read()); n_p = t1.name
                with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as t2: t2.write(sop_file.read()); s_p = t2.name
                
                docs = []
                for p in [n_p, s_p]: docs.extend(PyPDFLoader(p).load())
                splits = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=150).split_documents(docs)
                vstore = Chroma.from_documents(documents=splits, embedding=HuggingFaceEmbeddings(model_name="sentence-transformers/all-MiniLM-L6-v2"))
                
                llm = ChatGroq(model_name="llama-3.1-8b-instant", temperature=0)
                
                # Daftar Definisi Pilar NIST 2.0
                pilar_nist = [
                    ("GOVERN", "GV", "Strategi, tata kelola, dan manajemen risiko."),
                    ("IDENTIFY", "ID", "Inventarisasi aset, lingkungan bisnis, dan penilaian risiko."),
                    ("PROTECT", "PR", "Keamanan akses, kesadaran staf, dan perlindungan data."),
                    ("DETECT", "DE", "Pemantauan anomali dan deteksi kejadian keamanan."),
                    ("RESPOND", "RS", "Perencanaan respon insiden dan mitigasi."),
                    ("RECOVER", "RC", "Pemulihan layanan dan komunikasi pasca insiden.")
                ]
                
                all_results = []
                progress_bar = st.progress(0)
                
                # Looping untuk setiap pilar agar tidak kena limit TPM 6000
                # --- LOOPING ANALISIS DENGAN PENANGANAN ERROR LEBIH KUAT ---
                for idx, (nama, prefix, desc) in enumerate(pilar_nist):
                    st.write(f"🔎 Menganalisis Pilar: **{nama}**...")
                    
                    # Ambil konteks lebih banyak (k=4) untuk menghindari 'Konteks Kosong'
                    relevant_docs = vstore.as_retriever(search_kwargs={"k": 4}).invoke(f"Kontrol NIST {nama}: {desc}")
                    context_text = "\n\n".join([d.page_content for d in relevant_docs])
                    
                    # Prompt yang sangat ketat terhadap format
                    prompt = f"""
                    Anda adalah Auditor Senior NIST CSF 2.0.
                    Analisis pilar: {nama}
                    Konteks Dokumen: {context_text}

                    Tugas:
                    Bandingkan SOP dengan NIST. Jika tidak ada data di SOP, sebutkan gap tersebut secara detail.
                    
                    Ketentuan Penulisan:
                    - 'Current Situation': Jelaskan fakta kondisi SOP saat ini (20-30 kata).
                    - 'Action Plan': Jelaskan rekomendasi perbaikan (20-30 kata).

                    Format Wajib (HANYA HASIL INI, TANPA PENJELASAN LAIN):
                    {nama} | {prefix}.XX-01 | [Situasi 20-30 kata] | [Saran 20-30 kata]
                    """
                    
                    try:
                        resp = llm.invoke(prompt).content
                        
                        # Cek apakah ada hasil yang valid
                        found_in_pilar = False
                        for line in resp.strip().split('\n'):
                            if "|" in line:
                                parts = [p.strip() for p in line.split("|")]
                                if len(parts) >= 4:
                                    all_results.append(parts[:4])
                                    found_in_pilar = True
                        
                        if not found_in_pilar:
                            st.warning(f"⚠️ AI memberikan jawaban untuk {nama} tapi formatnya salah.")
                            
                    except Exception as e:
                        st.error(f"❌ Gagal memproses pilar {nama}: {str(e)}")
                    
                    # Jeda lebih lama (2 detik) untuk memastikan limit TPM 6000 tidak terlampaui
                    time.sleep(2) 
                    progress_bar.progress((idx + 1) / len(pilar_nist))

                # Konversi ke DataFrame
                df = pd.DataFrame(all_results, columns=["Fungsi", "ID", "Current Situation", "Action Plan"])
                df = df.drop_duplicates(subset=['ID'])

                if not df.empty:
                    st.success("✅ Audit Selesai!")
                    st.subheader("📋 Hasil Audit Mendalam")
                    st.table(df)

                    # Statistik & Visualisasi
                    nist_core = [p[0] for p in pilar_nist]
                    counts = df['Fungsi'].value_counts().reindex(nist_core, fill_value=0)
                    
                    st.subheader("📊 Statistik Kesenjangan")
                    fig, ax = plt.subplots(figsize=(10, 4))
                    counts.plot(kind='bar', ax=ax, color=['#4CAF50', '#2196F3', '#FFC107', '#FF5722', '#9C27B0', '#607D8B'])
                    st.pyplot(fig)
                    
                    buf = io.BytesIO()
                    plt.savefig(buf, format='png')

                    # Summary & Export
                    summary_txt = f"Total ditemukan {len(df)} gap unik. Prioritas utama perbaikan adalah pilar {counts.idxmax()}."
                    st.info(summary_txt)
                    
                    st.sidebar.divider()
                    st.sidebar.download_button("📊 Download Excel", df.to_csv(index=False).encode('utf-8'), "Audit_Report.csv")
                    st.sidebar.download_button("📄 Download PDF", create_pdf(df, summary_txt, buf), "Audit_Report.pdf")
                else:
                    st.error("AI tidak berhasil mengekstrak data. Coba gunakan dokumen yang lebih spesifik.")

            except Exception as e:
                st.error(f"Terjadi kesalahan: {e}")