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

# --- FUNGSI GENERATE PDF ---
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
    pdf.set_font("Arial", 'B', 8)
    pdf.cell(45, 10, "Fungsi", border=1)
    pdf.cell(25, 10, "ID NIST", border=1)
    pdf.cell(120, 10, "Action Plan (Rekomendasi)", border=1, ln=True)
    
    pdf.set_font("Arial", '', 7)
    for i in range(len(df)):
        pdf.cell(45, 10, str(df.iloc[i, 0]), border=1)
        pdf.cell(25, 10, str(df.iloc[i, 1]), border=1)
        pdf.cell(120, 10, str(df.iloc[i, 3])[:85], border=1, ln=True)
    return pdf.output(dest='S').encode('latin-1')

# --- SETUP API KEY ---
if "GROQ_API_KEY" in st.secrets:
    os.environ["GROQ_API_KEY"] = st.secrets["GROQ_API_KEY"]
else:
    os.environ["GROQ_API_KEY"] = "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"

st.set_page_config(page_title="AI Cyber-Auditor NIST CSF 2.0", layout="wide")
st.title("🛡️ AI Cyber-Auditor: NIST CSF 2.0 Expert Mode")

nist_file = st.sidebar.file_uploader("Upload Standar NIST CSF 2.0 (PDF)", type="pdf")
sop_file = st.sidebar.file_uploader("Upload SOP IT Kampus (PDF)", type="pdf")

if nist_file and sop_file:
    if st.button("🚀 Jalankan Audit Patuh Framework"):
        with st.spinner("Menganalisis dokumen..."):
            try:
                with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as t1: t1.write(nist_file.read()); n_p = t1.name
                with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as t2: t2.write(sop_file.read()); s_p = t2.name

                docs = []
                for p in [n_p, s_p]: docs.extend(PyPDFLoader(p).load())
                splits = RecursiveCharacterTextSplitter(chunk_size=1200, chunk_overlap=150).split_documents(docs)
                vstore = Chroma.from_documents(documents=splits, embedding=HuggingFaceEmbeddings(model_name="sentence-transformers/all-MiniLM-L6-v2"))
                retriever = vstore.as_retriever(search_kwargs={"k": 4})

                llm = ChatGroq(model_name="llama-3.1-8b-instant", temperature=0)

                template = """
                Anda adalah Auditor Senior NIST. Bandingkan SOP Kampus dengan Framework NIST CSF 2.0.
                Hasilkan laporan hanya dalam baris data dengan pemisah " | ".
                
                ATURAN KETAT:
                - Harus 4 kolom: Fungsi | ID NIST | Status Saat Ini | Action Plan
                - ID awalan 'GV' = GOVERN, 'ID' = IDENTIFY, 'PR' = PROTECT, 'DE' = DETECT, 'RS' = RESPOND, 'RC' = RECOVER.

                Konteks Dokumen: {context}
                """
                prompt = ChatPromptTemplate.from_template(template)
                chain = ({"context": retriever, "question": RunnablePassthrough()} | prompt | llm)
                
                res = chain.invoke("Lakukan audit gap analysis.").content

                # --- FIX: LOGIKA PARSING YANG AMAN ---
                rows = []
                for line in res.strip().split('\n'):
                    # Hanya ambil baris yang mengandung karakter pemisah "|"
                    if "|" in line:
                        parts = [p.strip() for p in line.split("|")]
                        # VALIDASI: Pastikan jumlah kolom tepat 4
                        if len(parts) == 4:
                            rows.append(parts)

                # Jika ada baris yang valid
                if rows:
                    df = pd.DataFrame(rows, columns=["Fungsi", "ID", "Current Status", "Action Plan"])

                    # Logika Sinkronisasi Fungsi (Mapping)
                    mapping = {'GV': 'GOVERN', 'ID': 'IDENTIFY', 'PR': 'PROTECT', 'DE': 'DETECT', 'RS': 'RESPOND', 'RC': 'RECOVER'}
                    def fix_function(row):
                        prefix = str(row['ID'])[:2].upper()
                        return mapping.get(prefix, row['Fungsi'].upper())
                    
                    df['Fungsi'] = df.apply(fix_function, axis=1)

                    st.success(f"✅ Audit Selesai: {len(df)} temuan gap terdeteksi.")
                    st.table(df)
                    
                    # Visualisasi & Summary
                    nist_core = ['GOVERN', 'IDENTIFY', 'PROTECT', 'DETECT', 'RESPOND', 'RECOVER']
                    counts = df['Fungsi'].value_counts().reindex(nist_core, fill_value=0)
                    top_issue = counts.idxmax()

                    st.subheader("📝 Ringkasan Eksekutif")
                    summary_text = f"Ditemukan {len(df)} titik gap. Area kritis utama: {top_issue}."
                    st.info(summary_text)

                    st.subheader("📊 Grafik Kepatuhan")
                    fig, ax = plt.subplots(figsize=(10, 4))
                    counts.plot(kind='bar', ax=ax, color=['#4CAF50', '#2196F3', '#FFC107', '#FF5722', '#9C27B0', '#607D8B'])
                    st.pyplot(fig)
                    
                    buf = io.BytesIO()
                    plt.savefig(buf, format='png')

                    st.sidebar.divider()
                    st.sidebar.download_button("📊 Excel", df.to_csv(index=False).encode('utf-8'), "Audit.csv")
                    st.sidebar.download_button("📄 PDF", create_pdf(df, summary_text, buf), "Audit.pdf")
                else:
                    st.error("AI menghasilkan format yang tidak sesuai (kurang dari 4 kolom). Silakan coba lagi.")

            except Exception as e:
                st.error(f"Kesalahan Sistem: {e}")