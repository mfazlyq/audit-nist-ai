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
    pdf.cell(45, 10, "Kategori", border=1)
    pdf.cell(25, 10, "ID", border=1)
    pdf.cell(120, 10, "Rencana Tindakan (Action Plan)", border=1, ln=True)
    
    pdf.set_font("Arial", '', 7)
    for i in range(len(df)):
        pdf.cell(45, 10, str(df.iloc[i, 0])[:25], border=1)
        pdf.cell(25, 10, str(df.iloc[i, 1]), border=1)
        pdf.cell(120, 10, str(df.iloc[i, 3])[:85], border=1, ln=True)
    return pdf.output(dest='S').encode('latin-1')

# --- SETUP API KEY ---
if "GROQ_API_KEY" in st.secrets:
    os.environ["GROQ_API_KEY"] = st.secrets["GROQ_API_KEY"]
else:
    os.environ["GROQ_API_KEY"] = "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"

st.set_page_config(page_title="AI Cyber-Auditor NIST CSF 2.0", layout="wide")
st.title("🛡️ AI Cyber-Auditor: NIST CSF 2.0 (Expert Auditor Mode)")

nist_file = st.sidebar.file_uploader("Upload Standar NIST CSF 2.0 (PDF)", type="pdf")
sop_file = st.sidebar.file_uploader("Upload SOP IT Kampus (PDF)", type="pdf")

if nist_file and sop_file:
    if st.button("🚀 Jalankan Analisis Ahli"):
        with st.spinner("Auditor sedang meninjau dokumen..."):
            try:
                with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as t1: t1.write(nist_file.read()); n_p = t1.name
                with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as t2: t2.write(sop_file.read()); s_p = t2.name

                docs = []
                for p in [n_p, s_p]: docs.extend(PyPDFLoader(p).load())
                
                splits = RecursiveCharacterTextSplitter(chunk_size=1200, chunk_overlap=150).split_documents(docs)
                vstore = Chroma.from_documents(documents=splits, embedding=HuggingFaceEmbeddings(model_name="sentence-transformers/all-MiniLM-L6-v2"))
                
                # Menggunakan k=3 agar tetap stabil di limit TPM 6000 Groq
                retriever = vstore.as_retriever(search_kwargs={"k": 3})

                llm = ChatGroq(model_name="llama-3.1-8b-instant", temperature=0)

                # --- PROMPT LOGIC AUDITOR SENIOR ---
                template = """
                Anda adalah Auditor Keamanan Siber Senior bersertifikasi (CISA/CISSP). 
                Tugas Anda adalah melakukan audit mendalam dengan membandingkan SOP IT Kampus terhadap Kerangka Kerja NIST CSF 2.0.

                Gunakan logika berikut untuk setiap kolom:
                1. FUNGSI/KATEGORI: Sebutkan Pilar NIST (GOVERN, IDENTIFY, PROTECT, DETECT, RESPOND, RECOVER).
                2. ID SUBKATEGORI: Sebutkan kode NIST yang relevan (Contoh: PR.AC-01).
                3. CURRENT STATUS: Jelaskan situasi nyata di SOP Kampus. Jika tidak ditemukan, katakan "Belum didokumentasikan dalam SOP".
                4. ACTION PLAN: Berikan rekomendasi langkah konkret berdasarkan standar NIST CSF 2.0 untuk menutupi celah tersebut.

                Format WAJIB: Kategori | ID | Status | Rencana Aksi
                Tugas: Temukan celah (gap) yang paling kritikal. Jangan berikan kalimat pembuka.
                
                Konteks: {context}
                """
                prompt = ChatPromptTemplate.from_template(template)
                chain = ({"context": retriever, "question": RunnablePassthrough()} | prompt | llm)
                
                res = chain.invoke("Lakukan audit gap analysis menyeluruh").content

                rows = []
                for line in res.strip().split('\n'):
                    parts = [p.strip() for p in line.split("|")]
                    if len(parts) >= 4:
                        rows.append(parts[:4])

                df = pd.DataFrame(rows, columns=["Fungsi", "ID", "Current Status", "Action Plan"])

                if not df.empty:
                    st.success(f"✅ Analisis Berhasil: Ditemukan {len(df)} celah keamanan.")
                    st.table(df)
                    
                    # Logika Statistik
                    nist_core = ['GOVERN', 'IDENTIFY', 'PROTECT', 'DETECT', 'RESPOND', 'RECOVER']
                    df['Main_Func'] = df['Fungsi'].str.upper().apply(lambda x: next((f for f in nist_core if f in x), 'LAINNYA'))
                    counts = df['Main_Func'].value_counts()
                    top_issue = counts.idxmax() if not counts.empty else "N/A"

                    # Summary Section
                    st.subheader("📝 Ringkasan Eksekutif")
                    summary_text = (
                        f"Berdasarkan tinjauan auditor:\n"
                        f"- **Current Situation**: Ditemukan {len(df)} ketidaksesuaian antara SOP Kampus dengan standar internasional.\n"
                        f"- **Titik Lemah Utama**: Area **{top_issue}** memerlukan perhatian mendesak.\n"
                        f"- **Kepatuhan NIST**: Rekomendasi pada 'Action Plan' disusun untuk meningkatkan kematangan siber sesuai NIST CSF 2.0."
                    )
                    st.info(summary_text)

                    # Visualisasi
                    st.subheader("📊 Statistik Kesenjangan NIST CSF 2.0")
                    plot_data = counts.reindex(nist_core, fill_value=0)
                    fig, ax = plt.subplots(figsize=(10, 4))
                    plot_data.plot(kind='bar', ax=ax, color=['#4CAF50', '#2196F3', '#FFC107', '#FF5722', '#9C27B0', '#607D8B'])
                    for i, v in enumerate(plot_data): ax.text(i, v + 0.1, str(int(v)), ha='center', fontweight='bold')
                    st.pyplot(fig)
                    
                    buf = io.BytesIO()
                    plt.savefig(buf, format='png')

                    # Export Sidebar
                    st.sidebar.divider()
                    st.sidebar.subheader("📥 Export Laporan")
                    
                    exc_buf = io.BytesIO()
                    with pd.ExcelWriter(exc_buf, engine='openpyxl') as w: df.to_excel(w, index=False)
                    st.sidebar.download_button("📊 Download Excel", exc_buf.getvalue(), "Audit_Report.xlsx")
                    
                    pdf_bytes = create_pdf(df, summary_text, buf)
                    st.sidebar.download_button("📄 Download PDF", pdf_bytes, "Audit_Report.pdf")
                else:
                    st.warning("AI tidak dapat membedah dokumen. Pastikan file PDF berisi teks yang dapat dibaca.")

            except Exception as e:
                st.error(f"Terjadi kesalahan teknis: {e}")
else:
    st.warning("⚠️ Silakan upload dokumen NIST dan SOP Kampus untuk memulai audit.")

st.divider()
st.caption("Prototipe AI Cyber-Auditor NIST CSF 2.0 - Penelitian Hibah Dosen Pemula 2024")