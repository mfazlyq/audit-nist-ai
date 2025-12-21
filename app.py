import streamlit as st
import os
import tempfile
import pandas as pd
import io
import matplotlib.pyplot as plt
from fpdf import FPDF 
from langchain_community.document_loaders import PyPDFLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_community.vectorstores import Chroma
from langchain_groq import ChatGroq
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import RunnablePassthrough

# --- 1. FUNGSI GENERATE PDF ---
def create_pdf(df, summary_text, plot_buf):
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", 'B', 16)
    pdf.cell(190, 10, "LAPORAN AUDIT KEPATUHAN NIST CSF 2.0", ln=True, align='C')
    pdf.ln(10)
    
    pdf.set_font("Arial", 'B', 12)
    pdf.cell(100, 10, "1. Ringkasan Eksekutif", ln=True)
    pdf.set_font("Arial", '', 10)
    pdf.multi_cell(190, 7, summary_text.replace("**", ""))
    pdf.ln(10)
    
    pdf.set_font("Arial", 'B', 12)
    pdf.cell(100, 10, "2. Visualisasi Gap Analysis", ln=True)
    with tempfile.NamedTemporaryFile(delete=False, suffix=".png") as tmp_img:
        tmp_img.write(plot_buf.getvalue())
        pdf.image(tmp_img.name, x=15, y=pdf.get_y(), w=170)
    
    pdf.add_page()
    pdf.set_font("Arial", 'B', 12)
    pdf.cell(100, 10, "3. Detail Temuan Audit", ln=True)
    pdf.ln(5)
    
    # Header Tabel PDF
    pdf.set_font("Arial", 'B', 8)
    pdf.set_fill_color(230, 230, 230)
    pdf.cell(40, 10, "Fungsi", border=1, fill=True)
    pdf.cell(20, 10, "ID", border=1, fill=True)
    pdf.cell(130, 10, "Rencana Tindakan", border=1, fill=True, ln=True)
    
    pdf.set_font("Arial", '', 7)
    for i in range(len(df)):
        pdf.cell(40, 10, str(df.iloc[i, 0])[:20], border=1)
        pdf.cell(20, 10, str(df.iloc[i, 1]), border=1)
        pdf.cell(130, 10, str(df.iloc[i, 3])[:90], border=1, ln=True)
    return pdf.output(dest='S').encode('latin-1')

# --- 2. SETUP API ---
if "GROQ_API_KEY" in st.secrets:
    os.environ["GROQ_API_KEY"] = st.secrets["GROQ_API_KEY"]
else:
    os.environ["GROQ_API_KEY"] = "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"

st.set_page_config(page_title="AI Cyber-Auditor NIST CSF 2.0", layout="wide")
st.title("🛡️ AI Cyber-Auditor: NIST CSF 2.0 Expert")

nist_file = st.sidebar.file_uploader("Standar NIST (PDF)", type="pdf")
sop_file = st.sidebar.file_uploader("SOP Kampus (PDF)", type="pdf")

if nist_file and sop_file:
    if st.button("🚀 Jalankan Audit Patuh Framework"):
        with st.spinner("Menganalisis dokumen..."):
            try:
                # Ingestion
                with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as t1: t1.write(nist_file.read()); n_p = t1.name
                with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as t2: t2.write(sop_file.read()); s_p = t2.name

                docs = []
                for p in [n_p, s_p]: docs.extend(PyPDFLoader(p).load())
                splits = RecursiveCharacterTextSplitter(chunk_size=1200, chunk_overlap=150).split_documents(docs)
                vstore = Chroma.from_documents(documents=splits, embedding=HuggingFaceEmbeddings(model_name="sentence-transformers/all-MiniLM-L6-v2"))
                retriever = vstore.as_retriever(search_kwargs={"k": 3})

                llm = ChatGroq(model_name="llama-3.1-8b-instant", temperature=0)

                # PROMPT DIPERKUAT (STRICT MODE)
                template = """
                Tugas: Auditor Senior NIST CSF 2.0.
                Output: HANYA baris data mentah. JANGAN ADA JUDUL, PENJELASAN, ATAU TABEL MARKDOWN.

                ATURAN KOLOM: Fungsi | ID | Status Saat Ini | Action Plan
                
                PEMETAAN FUNGSI (WAJIB):
                - ID awalan 'GV' -> GOVERN
                - ID awalan 'ID' -> IDENTIFY
                - ID awalan 'PR' -> PROTECT
                - ID awalan 'DE' -> DETECT
                - ID awalan 'RS' -> RESPOND
                - ID awalan 'RC' -> RECOVER

                Konteks: {context}
                """
                prompt = ChatPromptTemplate.from_template(template)
                chain = ({"context": retriever, "question": RunnablePassthrough()} | prompt | llm)
                
                res = chain.invoke("Lakukan audit gap analysis.").content

                # --- PARSING ROBUST (ANTI-ERROR) ---
                rows = []
                for line in res.strip().split('\n'):
                    # Lewati baris header/separator jika AI "bandel" memberikannya
                    if "---" in line or "Fungsi | ID" in line or not "|" in line:
                        continue
                    
                    # Bersihkan spasi dan ambil bagian kolom
                    parts = [p.strip() for p in line.split("|") if p.strip()]
                    
                    if len(parts) >= 4:
                        rows.append(parts[:4]) # Ambil hanya 4 kolom pertama

                if rows:
                    df = pd.DataFrame(rows, columns=["Fungsi", "ID", "Current Status", "Action Plan"])

                    # Mapping Correction (Agar Kategori Sinkron dengan ID)
                    map_nist = {'GV': 'GOVERN', 'ID': 'IDENTIFY', 'PR': 'PROTECT', 'DE': 'DETECT', 'RS': 'RESPOND', 'RC': 'RECOVER'}
                    def sync_func(row):
                        pref = str(row['ID'])[:2].upper()
                        return map_nist.get(pref, row['Fungsi'].upper())
                    df['Fungsi'] = df.apply(sync_func, axis=1)

                    st.success(f"✅ Berhasil memetakan {len(df)} temuan gap.")
                    st.table(df)
                    
                    # Visualisasi & Summary
                    nist_core = ['GOVERN', 'IDENTIFY', 'PROTECT', 'DETECT', 'RESPOND', 'RECOVER']
                    counts = df['Fungsi'].value_counts().reindex(nist_core, fill_value=0)
                    
                    st.subheader("📝 Ringkasan Eksekutif")
                    summary_text = f"Ditemukan {len(df)} gap. Pilar yang paling banyak celah adalah {counts.idxmax()}."
                    st.info(summary_text)

                    st.subheader("📊 Statistik Distribusi Gap")
                    fig, ax = plt.subplots(figsize=(10, 4))
                    counts.plot(kind='bar', ax=ax, color=['#4CAF50', '#2196F3', '#FFC107', '#FF5722', '#9C27B0', '#607D8B'])
                    for i, v in enumerate(counts): ax.text(i, v + 0.1, str(int(v)), ha='center', fontweight='bold')
                    st.pyplot(fig)
                    
                    buf = io.BytesIO()
                    plt.savefig(buf, format='png')

                    # Export
                    st.sidebar.divider()
                    st.sidebar.download_button("📊 Excel", df.to_csv(index=False).encode('utf-8'), "Audit_NIST.csv")
                    st.sidebar.download_button("📄 PDF", create_pdf(df, summary_text, buf), "Audit_NIST.pdf")
                else:
                    st.error("AI tidak memberikan data dalam format 4 kolom. Silakan tekan tombol 'Jalankan' lagi.")

            except Exception as e:
                st.error(f"Kesalahan Sistem: {e}")
else:
    st.info("💡 Unggah dokumen NIST dan SOP Kampus di sidebar untuk memulai.")