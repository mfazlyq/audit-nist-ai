import streamlit as st
import os
import tempfile
import pandas as pd
import io
from langchain_community.document_loaders import PyPDFLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_community.vectorstores import Chroma
from langchain_groq import ChatGroq
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import RunnablePassthrough
import matplotlib.pyplot as plt

# --- 1. KONFIGURASI KEAMANAN API KEY ---
if "GROQ_API_KEY" in st.secrets:
    os.environ["GROQ_API_KEY"] = st.secrets["GROQ_API_KEY"]
else:
    # Untuk testing lokal, masukkan API Key Anda di sini
    os.environ["GROQ_API_KEY"] = "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"

# --- 2. KONFIGURASI HALAMAN ---
st.set_page_config(page_title="AI Cyber-Auditor NIST CSF 2.0", layout="wide")

st.title("🛡️ AI Cyber-Auditor: NIST CSF 2.0 Compliance")
st.markdown("""
Aplikasi ini melakukan **Audit Kepatuhan Otomatis** dengan format standar **NIST Organizational Profile**.
""")

# --- 3. SIDEBAR UNTUK INPUT & DOWNLOAD ---
st.sidebar.header("📂 Data Audit")
nist_file = st.sidebar.file_uploader("Upload Standar NIST CSF 2.0 (PDF)", type="pdf")
sop_file = st.sidebar.file_uploader("Upload SOP IT Kampus (PDF)", type="pdf")

# --- 4. PROSES UTAMA RAG ---
if nist_file and sop_file:
    if st.button("🚀 Jalankan Analisis Audit"):
        with st.spinner("Sedang memetakan SOP ke standar NIST CSF 2.0..."):
            try:
                # Simpan file sementara
                with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp_nist:
                    tmp_nist.write(nist_file.getvalue())
                    nist_path = tmp_nist.name
                
                with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp_sop:
                    tmp_sop.write(sop_file.getvalue())
                    sop_path = tmp_sop.name

                # Load dokumen
                loaders = [PyPDFLoader(nist_path), PyPDFLoader(sop_path)]
                docs = []
                for loader in loaders:
                    docs.extend(loader.load())

                # Chunking (Pemisahan Teks)
                text_splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=150)
                splits = text_splitter.split_documents(docs)

                # Vector Store
                embeddings = HuggingFaceEmbeddings(model_name="sentence-transformers/all-MiniLM-L6-v2")
                vectorstore = Chroma.from_documents(documents=splits, embedding=embeddings)
                
                # Retriever (Optimasi k=3 agar tidak terkena limit TPM 6000 token)
                retriever = vectorstore.as_retriever(search_kwargs={"k": 3})

                # Inisiasi AI (Menggunakan model terbaru Llama 3.1)
                llm = ChatGroq(model_name="llama-3.1-8b-instant", temperature=0)

                # Prompt Engineering Berbasis Excel NIST Organizational Profile
                template = """
                Anda adalah Auditor Keamanan Siber Senior. 
                Tugas Anda adalah memetakan SOP IT Kampus ke dalam NIST CSF 2.0 Organizational Profile.

                Gunakan format laporan berikut untuk SETIAP temuan:

                1. FUNGSI & KATEGORI: (Contoh: PROTECT / Identity Management)
                2. NIST SUB-CATEGORY: (Contoh: PR.IR-01)
                3. DESCRIPTION OF CURRENT STATE: (Jelaskan apa yang tertulis di SOP Kampus saat ini terkait poin ini)
                4. GAP ANALYSIS: (Jelaskan apa yang kurang jika dibandingkan dengan standar NIST CSF 2.0)
                5. ACTION PLAN (TARGET STATE): (Berikan langkah konkret untuk mencapai standar tersebut)

                Konteks Dokumen: {context}
                Pertanyaan: {question}

                Berikan jawaban dalam Bahasa Indonesia yang sangat terstruktur.
                """
                prompt = ChatPromptTemplate.from_template(template)

                # RAG Chain
                rag_chain = (
                    {"context": retriever, "question": RunnablePassthrough()}
                    | prompt
                    | llm
                )

                # Eksekusi AI
                response = rag_chain.invoke("Lakukan audit gap analysis menyeluruh")

                # --- 5. TAMPILKAN HASIL ---
                st.success("✅ Analisis Selesai!")
                
                col_text, col_chart = st.columns([2, 1])

                with col_text:
                    st.subheader("📋 Laporan Pemetaan NIST Organizational Profile")
                    st.markdown(response.content)

                with col_chart:
                    st.subheader("📊 Statistik Kepatuhan")
                    fokus_nist = ['Govern', 'Identify', 'Protect', 'Detect', 'Respond', 'Recover']
                    skor = [70, 65, 50, 40, 55, 30] # Data simulasi
                    
                    fig, ax = plt.subplots()
                    ax.barh(fokus_nist, skor, color='#1f77b4')
                    ax.set_xlim(0, 100)
                    ax.set_xlabel('Persentase Kepatuhan (%)')
                    st.pyplot(fig)

                # --- 6. LOGIKA EXPORT EXCEL ---
                data_excel = {
                    "Kategori": ["Hasil Audit NIST CSF 2.0"],
                    "Hasil Analisis": [response.content]
                }
                df = pd.DataFrame(data_excel)
                output = io.BytesIO()
                with pd.ExcelWriter(output, engine='openpyxl') as writer:
                    df.to_excel(writer, index=False, sheet_name='Audit_Report')
                
                st.sidebar.divider()
                st.sidebar.subheader("📥 Download Laporan")
                st.sidebar.download_button(
                    label="Download Laporan (Excel)",
                    data=output.getvalue(),
                    file_name="Audit_NIST_CSF_Profile.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                )

            except Exception as e:
                st.error(f"Terjadi kesalahan teknis: {e}")
else:
    st.warning("⚠️ Silakan upload file PDF di sidebar untuk memulai.")

st.divider()
st.caption("Penelitian Hibah Dosen Pemula 2024 - AI for Cybersecurity Compliance")