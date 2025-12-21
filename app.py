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

# --- 1. KONFIGURASI API KEY ---
if "GROQ_API_KEY" in st.secrets:
    os.environ["GROQ_API_KEY"] = st.secrets["GROQ_API_KEY"]
else:
    os.environ["GROQ_API_KEY"] = "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"

st.set_page_config(page_title="AI Cyber-Auditor NIST CSF 2.0", layout="wide")
st.title("🛡️ AI Cyber-Auditor: NIST CSF 2.0 Compliance")

# --- FUNGSI GENERATE PDF ---
def create_pdf(df, summary_text, plot_buf):
    pdf = FPDF()
    pdf.add_page()
    
    # Header
    pdf.set_font("Arial", 'B', 16)
    pdf.cell(190, 10, "Laporan Audit NIST CSF 2.0", ln=True, align='C')
    pdf.ln(10)
    
    # Summary Section
    pdf.set_font("Arial", 'B', 12)
    pdf.cell(100, 10, "1. Ringkasan Eksekutif", ln=True)
    pdf.set_font("Arial", '', 10)
    pdf.multi_cell(190, 7, summary_text.replace("**", "")) # Hapus markdown bold untuk PDF
    pdf.ln(10)
    
    # Visualization Section
    pdf.set_font("Arial", 'B', 12)
    pdf.cell(100, 10, "2. Visualisasi Gap Analysis", ln=True)
    # Simpan plot ke file temporary untuk dimasukkan ke PDF
    with tempfile.NamedTemporaryFile(delete=False, suffix=".png") as tmpfile:
        tmpfile.write(plot_buf.getvalue())
        pdf.image(tmpfile.name, x=10, y=pdf.get_y(), w=180)
    pdf.ln(100) # Beri jarak setelah gambar
    
    # Table Section (Hanya 3 kolom utama agar muat di PDF)
    pdf.add_page()
    pdf.set_font("Arial", 'B', 12)
    pdf.cell(100, 10, "3. Detail Temuan Gap", ln=True)
    pdf.set_font("Arial", 'B', 8)
    
    # Header Tabel
    pdf.cell(40, 10, "Fungsi", border=1)
    pdf.cell(30, 10, "ID", border=1)
    pdf.cell(120, 10, "Action Plan", border=1, ln=True)
    
    # Isi Tabel
    pdf.set_font("Arial", '', 7)
    for i in range(len(df)):
        pdf.cell(40, 10, str(df.iloc[i, 0])[:25], border=1)
        pdf.cell(30, 10, str(df.iloc[i, 1]), border=1)
        pdf.cell(120, 10, str(df.iloc[i, 3])[:80], border=1, ln=True)
        
    return pdf.output(dest='S').encode('latin-1')

# --- 2. SIDEBAR ---
st.sidebar.header("📂 Data Audit")
nist_file = st.sidebar.file_uploader("Upload Standar NIST CSF 2.0 (PDF)", type="pdf")
sop_file = st.sidebar.file_uploader("Upload SOP IT Kampus (PDF)", type="pdf")

# --- 3. PROSES UTAMA ---
if nist_file and sop_file:
    if st.button("🚀 Jalankan Analisis Lengkap"):
        with st.spinner("Menganalisis dokumen..."):
            try:
                with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp_nist:
                    tmp_nist.write(nist_file.getvalue()); nist_path = tmp_nist.name
                with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp_sop:
                    tmp_sop.write(sop_file.getvalue()); sop_path = tmp_sop.name

                loaders = [PyPDFLoader(nist_path), PyPDFLoader(sop_path)]
                docs = []
                for loader in loaders: docs.extend(loader.load())

                text_splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=150)
                splits = text_splitter.split_documents(docs)
                embeddings = HuggingFaceEmbeddings(model_name="sentence-transformers/all-MiniLM-L6-v2")
                vectorstore = Chroma.from_documents(documents=splits, embedding=embeddings)
                retriever = vectorstore.as_retriever(search_kwargs={"k": 5})

                llm = ChatGroq(model_name="llama-3.1-8b-instant", temperature=0)

                template = """
                Anda adalah Auditor Keamanan Siber Senior. Berikan analisis gap dalam format baris per baris.
                Gunakan pemisah " | " untuk setiap kolom.
                
                Format setiap baris harus:
                Kategori | Subkategori | Current Status | Action Plan
                
                Pastikan Kategori dimulai dengan salah satu fungsi NIST: GOVERN, IDENTIFY, PROTECT, DETECT, RESPOND, atau RECOVER.
                
                Konteks: {context}
                Tugas: Temukan semua gap antara SOP dan NIST CSF 2.0. Berikan jawaban HANYA dalam format baris-baris tersebut.
                """
                prompt = ChatPromptTemplate.from_template(template)
                rag_chain = ({"context": retriever, "question": RunnablePassthrough()} | prompt | llm)
                
                response = rag_chain.invoke("Lakukan audit gap analysis")
                raw_text = response.content

                rows = []
                for line in raw_text.strip().split('\n'):
                    if "|" in line:
                        parts = [p.strip() for p in line.split("|")]
                        if len(parts) >= 4: rows.append(parts[:4])

                df = pd.DataFrame(rows, columns=["CSF Function/Category", "Subcategory ID", "Current Status", "Action Plan"])

                # --- OUTPUT STREAMLIT ---
                st.success("✅ Analisis Selesai!")
                st.subheader("📋 Tabel Temuan Gap Analysis")
                st.table(df)

                st.divider()

                # --- SUMMARY ---
                st.subheader("📝 Ringkasan Eksekutif")
                nist_core = ['GOVERN', 'IDENTIFY', 'PROTECT', 'DETECT', 'RESPOND', 'RECOVER']
                df['Main_Func'] = df['CSF Function/Category'].str.upper().apply(lambda x: next((f for f in nist_core if f in x), 'OTHER'))
                counts = df['Main_Func'].value_counts()
                top_issue = counts.idxmax() if not counts.empty else "N/A"
                
                summary_text = f"Total Temuan: {len(df)} gap. Area kritis: {top_issue}. SOP memerlukan perbaikan segera."
                st.info(summary_text)

                # --- VISUALISASI ---
                st.subheader("📊 Statistik Distribusi Gap")
                plot_data = counts.reindex(nist_core, fill_value=0)
                fig, ax = plt.subplots(figsize=(10, 5))
                plot_data.plot(kind='bar', ax=ax, color='#1f77b4')
                plt.xticks(rotation=0)
                
                # Simpan plot ke buffer untuk PDF
                buf = io.BytesIO()
                plt.savefig(buf, format='png')
                st.pyplot(fig)

                # --- EXPORT SECTION ---
                pdf_data = create_pdf(df, summary_text, buf)
                
                st.sidebar.divider()
                st.sidebar.subheader("📥 Export Laporan")
                st.sidebar.download_button(
                    label="Download Laporan (PDF)",
                    data=pdf_data,
                    file_name="Laporan_Audit_NIST.pdf",
                    mime="application/pdf"
                )
                
                # Tetap sediakan Excel
                output_exc = io.BytesIO()
                with pd.ExcelWriter(output_exc, engine='openpyxl') as writer:
                    df.drop(columns=['Main_Func']).to_excel(writer, index=False)
                st.sidebar.download_button("Download Laporan (Excel)", output_exc.getvalue(), "Laporan_Audit_NIST.xlsx")

            except Exception as e:
                st.error(f"Error: {e}")