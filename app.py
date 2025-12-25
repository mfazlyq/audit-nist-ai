import streamlit as st
import os
import tempfile
import pandas as pd
import io
import time
import hashlib 
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

def get_file_hash(file_bytes):
    return hashlib.sha256(file_bytes).hexdigest()

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

nist_file = st.sidebar.file_uploader("Upload Standar NIST (PDF)", type="pdf")
sop_file = st.sidebar.file_uploader("Upload SOP Kampus (PDF)", type="pdf")

if "audit_cache" not in st.session_state:
    st.session_state.audit_cache = {}

if nist_file and sop_file:
    sop_bytes = sop_file.getvalue()
    file_id = get_file_hash(sop_bytes)
    
    if st.button("🚀 Analisa 12 Gap Prioritas Utama"):
        if file_id in st.session_state.audit_cache:
            st.info("ℹ️ File terdeteksi. Mengambil data konsisten dari memori...")
        else:
            with st.spinner("Mengevaluasi celah keamanan dengan Standar ID NIST Asli..."):
                try:
                    with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as t1: t1.write(nist_file.read()); n_p = t1.name
                    with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as t2: t2.write(sop_bytes); s_p = t2.name
                    
                    docs = []
                    for p in [n_p, s_p]: docs.extend(PyPDFLoader(p).load())
                    splits = RecursiveCharacterTextSplitter(chunk_size=1200, chunk_overlap=200).split_documents(docs)
                    vstore = Chroma.from_documents(documents=splits, embedding=HuggingFaceEmbeddings(model_name="sentence-transformers/all-MiniLM-L6-v2"))
                    
                    llm = ChatGroq(model_name="llama-3.3-70b-versatile", temperature=0)
                    pilar_nist = ["GOVERN", "IDENTIFY", "PROTECT", "DETECT", "RESPOND", "RECOVER"]
                    
                    relevant_docs = vstore.as_retriever(search_kwargs={"k": 15}).invoke("Gaps analysis NIST CSF 2.0 subcategories")
                    context_text = "\n\n".join([d.page_content for d in relevant_docs])
                    
                    # --- PROMPT EKSTRIM (UNTUK MENGHENTIKAN HALUSINASI) ---
                    prompt = f"""
                    TUGAS: Auditor NIST Ahli. Temukan 12 GAP PALING KRITIS (Ranking 1-12).
                    KONTEKS SOP: {context_text}
                    
                    REFERENSI ID WAJIB (HANYA GUNAKAN INI):
                    - GOVERN: GV.OC, GV.RM, GV.RR, GV.PO, GV.OV, GV.SC
                    - IDENTIFY: ID.AM, ID.RA, ID.IM
                    - PROTECT: PR.AA, PR.AT, PR.DS, PR.PS, PR.IR
                    - DETECT: DE.AE, DE.CM
                    - RESPOND: RS.CO, RS.AN, RS.MI, RS.MA
                    - RECOVER: RC.RP, RC.CO

                    INSTRUKSI KETAT:
                    1. ID_KONTROL: Wajib ambil dari daftar di atas + nomor (Contoh: PR.DS-01). Dilarang mengarang XX atau kode lain.
                    2. SITUASI & SARAN: Wajib terdiri dari 10 sampai 15 kata. Jangan lebih, jangan kurang.
                    3. PILAR: Wajib satu kata (GOVERN/IDENTIFY/PROTECT/DETECT/RESPOND/RECOVER).

                    FORMAT OUTPUT (WAJIB 12 BARIS):
                    PILAR | ID_KONTROL | Situasi | Saran
                    """
                    
                    resp = llm.invoke(prompt).content
                    all_results = []
                    
                    # Referensi Resmi untuk Validasi Python
                    valid_ids = ["GV.OC", "GV.RM", "GV.RR", "GV.PO", "GV.OV", "GV.SC", "ID.AM", "ID.RA", "ID.IM", 
                                 "PR.AA", "PR.AT", "PR.DS", "PR.PS", "PR.IR", "DE.AE", "DE.CM", 
                                 "RS.CO", "RS.AN", "RS.MI", "RS.MA", "RC.RP", "RC.CO"]

                    for line in resp.strip().split('\n'):
                        if "|" in line:
                            parts = [p.strip() for p in line.split("|")]
                            if len(parts) >= 4:
                                pilar_upper = parts[0].upper()
                                # Validasi Pilar & ID
                                matched_pilar = next((p for p in pilar_nist if p in pilar_upper), None)
                                id_val = parts[1].upper()
                                
                                # Hanya masukkan jika ID diawali dengan referensi asli
                                if matched_pilar and any(id_val.startswith(ref) for ref in valid_ids):
                                    all_results.append([matched_pilar, id_val, parts[2], parts[3]])
                    
                    if all_results:
                        st.session_state.audit_cache[file_id] = all_results[:12]
                except Exception as e:
                    st.error(f"Error: {e}")

    # --- TAMPILAN ---
    if file_id in st.session_state.audit_cache:
        current_data = st.session_state.audit_cache[file_id]
        df = pd.DataFrame(current_data, columns=["Fungsi", "ID", "Current Situation", "Action Plan"])
        
        st.success("✅ Analisis 12 Gap Prioritas Utama (Skala 1-12 Terkunci)")
        st.table(df)

        # --- RADAR CHART SINKRON ---
        st.subheader("📊 NIST Compliance Radar")
        pilar_labels = ["GOVERN", "IDENTIFY", "PROTECT", "DETECT", "RESPOND", "RECOVER"]
        counts = df['Fungsi'].value_counts().reindex(pilar_labels, fill_value=0)
        
        labels = np.array(pilar_labels)
        stats = np.concatenate((counts.values, [counts.values[0]]))
        angles = np.concatenate((np.linspace(0, 2*np.pi, len(labels), endpoint=False), [0]))

        fig, ax = plt.subplots(figsize=(5, 5), subplot_kw=dict(polar=True))
        ax.fill(angles, stats, color='red', alpha=0.3)
        ax.plot(angles, stats, color='red', linewidth=1.5, marker='o')
        ax.set_xticks(angles[:-1])
        ax.set_xticklabels(labels, size=8)
        
        max_y = int(stats.max()) if stats.max() > 0 else 1
        ax.set_yticks(range(0, max_y + 1))
        
        st.pyplot(fig)
        
        buf = io.BytesIO()
        plt.savefig(buf, format='png', bbox_inches='tight')
        st.sidebar.download_button("📄 PDF Report", create_pdf(df, "Audit Priority Report", buf), "Audit.pdf")
else:
    st.info("👋 Silakan unggah file PDF.")