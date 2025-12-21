import streamlit as st
import os
import tempfile
import pandas as pd
import io
import re
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
    pdf.cell(190, 10, "Laporan Audit NIST CSF 2.0", ln=True, align='C')
    pdf.ln(10)
    
    # Summary
    pdf.set_font("Arial", 'B', 12)
    pdf.cell(100, 10, "1. Ringkasan Eksekutif", ln=True)
    pdf.set_font("Arial", '', 10)
    pdf.multi_cell(190, 7, summary_text.replace("**", ""))
    pdf.ln(10)
    
    # Visualization
    pdf.set_font("Arial", 'B', 12)
    pdf.cell(100, 10, "2. Statistik Distribusi Gap", ln=True)
    with tempfile.NamedTemporaryFile(delete=False, suffix=".png") as tmp_img:
        tmp_img.write(plot_buf.getvalue())
        pdf.image(tmp_img.name, x=15, y=pdf.get_y(), w=170)
    
    # Table (New Page)
    pdf.add_page()
    pdf.set_font("Arial", 'B', 12)
    pdf.cell(100, 10, "3. Tabel Temuan Gap Analysis", ln=True)
    pdf.set_font("Arial", 'B', 8)
    pdf.set_fill_color(200, 220, 255)
    pdf.cell(45, 10, "Fungsi/Kategori", border=1, fill=True)
    pdf.cell(25, 10, "ID", border=1, fill=True)
    pdf.cell(120, 10, "Rencana Tindakan (Action Plan)", border=1, fill=True, ln=True)
    
    pdf.set_font("Arial", '', 7)
    for i in range(len(df)):
        pdf.cell(45, 10, str(df.iloc[i, 0])[:25], border=1)
        pdf.cell(25, 10, str(df.iloc[i, 1]), border=1)
        pdf.cell(120, 10, str(df.iloc[i, 3])[:85], border=1, ln=True)
    return pdf.output(dest='S').encode('latin-1')

# --- 2. SETUP PAGE ---
if "GROQ_API_KEY" in st.secrets:
    os.environ["GROQ_API_KEY"] = st.secrets["GROQ_API_KEY"]
else:
    os.environ["GROQ_API_KEY"] = "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"

st.set_page_config(page_title="AI Cyber-Auditor NIST CSF 2.0", layout="wide")
st.title("🛡️ AI Cyber-Auditor: NIST CSF 2.0 Compliance")

# --- 3. SIDEBAR ---
st.sidebar.header("📂 Data Audit")
nist_file = st.sidebar.file_uploader("Upload Standar NIST CSF 2.0 (PDF)", type="pdf")
sop_file = st.sidebar.file_uploader("Upload SOP IT Kampus (PDF)", type="pdf")

if nist_file and sop_file:
    if st.button("🚀 Jalankan Analisis Lengkap"):
        with st.spinner("Menganalisis dan memproses visualisasi..."):
            try:
                # Ingestion
                with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as t1: t1.write(nist_file.read()); n_p = t1.name
                with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as t2: t2.write(sop_file.read()); s_p = t2.name

                docs = []
                for p in [n_p, s_p]: docs.extend(PyPDFLoader(p).load())
                splits = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=150).split_documents(docs)
                vstore = Chroma.from_documents(documents=splits, embedding=HuggingFaceEmbeddings(model_name="sentence-transformers/all-MiniLM-L6-v2"))
                retriever = vstore.as_retriever(search_kwargs={"k": 5})

                llm = ChatGroq(model_name="llama-3.1-8b-instant", temperature=0)

                # PROMPT DIPERKUAT UNTUK FIX KOLOM KOSONG
                template = """
                Anda adalah Auditor Senior. Berikan analisis gap antara SOP dan NIST CSF 2.0.
                WAJIB menggunakan format baris per baris dengan pemisah " | ".
                
                Format: Fungsi/Kategori | ID Subkategori | Status Saat Ini | Rencana Aksi
                
                CONTOH:
                PROTECT | PR.AC-01 | Tidak ada MFA | Implementasi MFA
                
                Konteks: {context}
                Tugas: Temukan semua gap. Jangan berikan teks penjelasan, hanya baris tabel.
                """
                prompt = ChatPromptTemplate.from_template(template)
                rag_chain = ({"context": retriever, "question": RunnablePassthrough()} | prompt | llm)
                
                response = rag_chain.invoke("Lakukan audit")
                raw_text = response.content

                # --- 4. PARSING DATA (FIX KOLOM KOSONG) ---
                rows = []
                for line in raw_text.strip().split('\n'):
                    parts = [p.strip() for p in line.split("|") if p.strip()]
                    if len(parts) >= 4:
                        rows.append(parts[:4])

                df = pd.DataFrame(rows, columns=["CSF Function/Category", "Subcategory ID", "Current Status", "Action Plan"])

                if not df.empty:
                    st.success(f"✅ Analisis Selesai! Ditemukan {len(df)} gap.")
                    st.table(df)
                    st.divider()

                    # --- 5. SUMMARY ---
                    nist_core = ['GOVERN', 'IDENTIFY', 'PROTECT', 'DETECT', 'RESPOND', 'RECOVER']
                    df['Main_Func'] = df['CSF Function/Category'].str.upper().apply(lambda x: next((f for f in nist_core if f in x), 'LAINNYA'))
                    counts = df['Main_Func'].value_counts()
                    top_issue = counts.idxmax() if not counts.empty else "N/A"

                    summary_text = (
                        f"Berdasarkan analisis audit:\n"
                        f"- Total Temuan: {len(df)} celah keamanan.\n"
                        f"- Area Paling Kritis: Fungsi {top_issue}.\n"
                        f"- Rekomendasi: Update SOP sesuai kolom Action Plan."
                    )
                    st.info(summary_text)

                    # --- 6. VISUALISASI (FIX TIDAK MUNCUL) ---
                    st.subheader("📊 Statistik Distribusi Gap")
                    plot_data = counts.reindex(nist_core, fill_value=0)
                    fig, ax = plt.subplots(figsize=(10, 5))
                    plot_data.plot(kind='bar', ax=ax, color=['#4CAF50', '#2196F3', '#FFC107', '#FF5722', '#9C27B0', '#607D8B'])
                    ax.set_title('Jumlah Gap per Fungsi NIST')
                    for i, v in enumerate(plot_data): ax.text(i, v + 0.1, str(int(v)), ha='center', fontweight='bold')
                    
                    buf = io.BytesIO()
                    plt.savefig(buf, format='png')
                    st.pyplot(fig)

                    # --- 7. EXPORT ---
                    st.sidebar.divider()
                    st.sidebar.subheader("📥 Export Hasil")
                    
                    # Excel
                    exc_buf = io.BytesIO()
                    with pd.ExcelWriter(exc_buf, engine='openpyxl') as w: df.to_excel(w, index=False)
                    st.sidebar.download_button("📥 Download Excel", exc_buf.getvalue(), "Audit_NIST.xlsx")

                    # PDF
                    pdf_bytes = create_pdf(df, summary_text, buf)
                    st.sidebar.download_button("📥 Download PDF", pdf_bytes, "Laporan_Audit_NIST.pdf")
                else:
                    st.error("AI tidak dapat memformat data dengan benar. Coba jalankan ulang.")

            except Exception as e:
                st.error(f"Kesalahan teknis: {e}")