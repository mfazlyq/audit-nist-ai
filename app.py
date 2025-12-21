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
    pdf.cell(100, 10, "3. Detail Temuan", ln=True)
    pdf.set_font("Arial", 'B', 8)
    pdf.cell(45, 10, "Kategori", border=1)
    pdf.cell(25, 10, "ID", border=1)
    pdf.cell(120, 10, "Rencana Tindakan", border=1, ln=True)
    
    pdf.set_font("Arial", '', 7)
    for i in range(len(df)):
        pdf.cell(45, 10, str(df.iloc[i, 0])[:25], border=1)
        pdf.cell(25, 10, str(df.iloc[i, 1]), border=1)
        pdf.cell(120, 10, str(df.iloc[i, 3])[:85], border=1, ln=True)
    return pdf.output(dest='S').encode('latin-1')

# --- SETUP ---
if "GROQ_API_KEY" in st.secrets:
    os.environ["GROQ_API_KEY"] = st.secrets["GROQ_API_KEY"]
else:
    os.environ["GROQ_API_KEY"] = "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"

st.set_page_config(page_title="AI Cyber-Auditor NIST CSF 2.0", layout="wide")
st.title("🛡️ AI Cyber-Auditor: NIST CSF 2.0 (Token Optimized)")

nist_file = st.sidebar.file_uploader("Upload Standar NIST CSF 2.0", type="pdf")
sop_file = st.sidebar.file_uploader("Upload SOP IT Kampus", type="pdf")

if nist_file and sop_file:
    if st.button("🚀 Jalankan Audit (Mode Hemat Token)"):
        with st.spinner("Sedang memproses dokumen agar sesuai limit Groq..."):
            try:
                with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as t1: t1.write(nist_file.read()); n_p = t1.name
                with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as t2: t2.write(sop_file.read()); s_p = t2.name

                docs = []
                for p in [n_p, s_p]: docs.extend(PyPDFLoader(p).load())
                
                # OPTIMASI 1: Chunking sedikit lebih besar untuk mengurangi jumlah potongan teks
                splits = RecursiveCharacterTextSplitter(chunk_size=1200, chunk_overlap=100).split_documents(docs)
                vstore = Chroma.from_documents(documents=splits, embedding=HuggingFaceEmbeddings(model_name="sentence-transformers/all-MiniLM-L6-v2"))
                
                # OPTIMASI 2: Mengurangi nilai k (dari 15 ke 3) agar token tidak meledak (FIX ERROR 413)
                retriever = vstore.as_retriever(search_kwargs={"k": 3})

                llm = ChatGroq(model_name="llama-3.1-8b-instant", temperature=0)

                template = """
                Anda adalah Auditor Senior. Petakan SOP ke NIST CSF 2.0.
                Hasilkan laporan hanya dalam baris data pemisah " | ".
                
                Format: Fungsi/Kategori | ID Subkategori | Status Saat Ini | Rencana Aksi
                Fungsi WAJIB salah satu: GOVERN, IDENTIFY, PROTECT, DETECT, RESPOND, RECOVER.
                
                Konteks: {context}
                Tugas: Temukan celah (gap). Jangan berikan teks pembuka/penutup.
                """
                prompt = ChatPromptTemplate.from_template(template)
                chain = ({"context": retriever, "question": RunnablePassthrough()} | prompt | llm)
                
                res = chain.invoke("Lakukan audit").content

                rows = []
                for line in res.strip().split('\n'):
                    parts = [p.strip() for p in line.split("|")]
                    if len(parts) >= 4: rows.append(parts[:4])

                df = pd.DataFrame(rows, columns=["Fungsi", "ID", "Current Status", "Action Plan"])

                if not df.empty:
                    st.success(f"✅ Berhasil menemukan {len(df)} titik gap analisis.")
                    st.table(df)
                    
                    nist_core = ['GOVERN', 'IDENTIFY', 'PROTECT', 'DETECT', 'RESPOND', 'RECOVER']
                    df['Main_Func'] = df['Fungsi'].str.upper().apply(lambda x: next((f for f in nist_core if f in x), 'OTHER'))
                    counts = df['Main_Func'].value_counts()
                    
                    summary_text = f"Total {len(df)} temuan. Fokus utama perbaikan pada fungsi {counts.idxmax()}."
                    st.info(summary_text)

                    plot_data = counts.reindex(nist_core, fill_value=0)
                    fig, ax = plt.subplots(figsize=(10, 4))
                    plot_data.plot(kind='bar', ax=ax, color='#1f77b4')
                    for i, v in enumerate(plot_data): ax.text(i, v + 0.1, str(int(v)), ha='center')
                    st.pyplot(fig)
                    
                    buf = io.BytesIO()
                    plt.savefig(buf, format='png')

                    exc_buf = io.BytesIO()
                    with pd.ExcelWriter(exc_buf, engine='openpyxl') as w: df.to_excel(w, index=False)
                    st.sidebar.download_button("📥 Excel", exc_buf.getvalue(), "Audit.xlsx")
                    
                    pdf_bytes = create_pdf(df, summary_text, buf)
                    st.sidebar.download_button("📥 PDF", pdf_bytes, "Audit.pdf")
                else:
                    st.warning("AI tidak dapat memformat data. Silakan coba lagi.")

            except Exception as e:
                st.error(f"Error: {e}")