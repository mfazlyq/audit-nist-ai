import streamlit as st
import os
import tempfile
import pandas as pd
import io
import time
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

if nist_file and sop_file:
    if st.button("🚀 Analisa 12 Gap Prioritas Utama"):
        with st.spinner("Mengevaluasi celah keamanan kritis..."):
            try:
                with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as t1: t1.write(nist_file.read()); n_p = t1.name
                with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as t2: t2.write(sop_file.read()); s_p = t2.name
                
                docs = []
                for p in [n_p, s_p]: docs.extend(PyPDFLoader(p).load())
                splits = RecursiveCharacterTextSplitter(chunk_size=1200, chunk_overlap=200).split_documents(docs)
                vstore = Chroma.from_documents(documents=splits, embedding=HuggingFaceEmbeddings(model_name="sentence-transformers/all-MiniLM-L6-v2"))
                
                # Menggunakan model stabil terbaru
                llm = ChatGroq(model_name="llama-3.3-70b-versatile", temperature=0)
                
                pilar_nist = ["GOVERN", "IDENTIFY", "PROTECT", "DETECT", "RESPOND", "RECOVER"]
                
                relevant_docs = vstore.as_retriever(search_kwargs={"k": 15}).invoke("Cari celah keamanan paling kritis dalam SOP berdasarkan standar NIST CSF 2.0")
                context_text = "\n\n".join([d.page_content for d in relevant_docs])
                
                # PROMPT DIPERKETAT UNTUK KONSISTENSI GRAFIK DAN JUMLAH KATA
                prompt = f"""
                TUGAS: Auditor Keamanan Senior. Temukan 12 GAP PALING KRITIS secara keseluruhan.
                KONTEKS: {context_text}
                
                INSTRUKSI KHUSUS:
                1. Identifikasi 12 temuan paling berbahaya (Global Ranking).
                2. PILAR wajib salah satu dari: GOVERN, IDENTIFY, PROTECT, DETECT, RESPOND, RECOVER.
                3. SITUASI: Jelaskan kekurangan SOP (WAJIB 10-15 kata).
                4. SARAN: Berikan langkah mitigasi (WAJIB 10-15 kata).

                FORMAT OUTPUT (WAJIB 12 BARIS):
                PILAR | ID_KONTROL | Situasi | Saran
                
                Contoh:
                PROTECT | PR.AC-01 | SOP belum mengatur penggunaan multifactor authentication untuk akses data sensitif admin. | Segera implementasikan MFA pada seluruh sistem akses kontrol untuk meningkatkan keamanan login.
                """
                
                resp = llm.invoke(prompt).content
                all_results = []
                for line in resp.strip().split('\n'):
                    if "|" in line and len(line.split("|")) >= 4:
                        parts = [p.strip() for p in line.split("|")]
                        # Validasi agar pilar sesuai untuk grafik
                        pilar_raw = parts[0].upper()
                        matched_pilar = next((p for p in pilar_nist if p in pilar_raw), None)
                        if matched_pilar:
                            all_results.append([matched_pilar, parts[1], parts[2], parts[3]])
                
                if all_results:
                    df = pd.DataFrame(all_results[:12], columns=["Fungsi", "ID", "Current Situation", "Action Plan"])
                    st.success("✅ Berhasil Menganalisis 12 Gap Prioritas Utama")
                    st.table(df)

                    # --- VISUALISASI SPIDER DIAGRAM (Sinkronisasi Penuh) ---
                    st.subheader("📊 NIST Compliance Gap Intensity Radar")
                    
                    # Hitung distribusi berdasarkan kolom 'Fungsi' yang sudah divalidasi
                    counts = df['Fungsi'].value_counts().reindex(pilar_nist, fill_value=0)
                    
                    labels = np.array(pilar_nist)
                    stats = counts.values
                    angles = np.linspace(0, 2*np.pi, len(labels), endpoint=False).tolist()
                    
                    # Tutup Loop
                    stats = np.concatenate((stats, [stats[0]]))
                    angles = np.concatenate((angles, [angles[0]]))

                    fig, ax = plt.subplots(figsize=(5, 5), subplot_kw=dict(polar=True))
                    ax.fill(angles, stats, color='red', alpha=0.3)
                    ax.plot(angles, stats, color='red', linewidth=1.5, marker='o', markersize=4)
                    
                    ax.set_xticks(angles[:-1])
                    ax.set_xticklabels(labels, size=8)
                    
                    # Dinamisasi Y-Axis berdasarkan jumlah temuan
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
                    st.error("Format audit tidak terbaca. Silakan ulangi proses.")

            except Exception as e:
                st.error(f"Terjadi kesalahan: {e}")
else:
    st.info("👋 Silakan unggah file PDF untuk memulai audit.")

st.divider()
st.caption("Prototipe Sistem Audit Otomatis NIST CSF 2.0 - 2025")