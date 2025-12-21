import streamlit as st
import os
import tempfile
from langchain_community.document_loaders import PyPDFLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_community.embeddings import HuggingFaceEmbeddings
from langchain_community.vectorstores import Chroma
from langchain_groq import ChatGroq
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import RunnablePassthrough
import matplotlib.pyplot as plt

# --- 1. KONFIGURASI KEAMANAN API KEY ---
# Mengambil API Key dari Streamlit Secrets (Aman untuk GitHub)
if "GROQ_API_KEY" in st.secrets:
    os.environ["GROQ_API_KEY"] = st.secrets["GROQ_API_KEY"]
else:
    # Jika dijalankan di laptop sendiri, pastikan API Key ada di environment variable
    # Atau masukkan sementara di sini untuk testing lokal:
    os.environ["GROQ_API_KEY"] = "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"

# --- 2. KONFIGURASI HALAMAN ---
st.set_page_config(page_title="AI Cyber-Auditor NIST CSF 2.0", layout="wide")

st.title("🛡️ AI Cyber-Auditor: NIST CSF 2.0 Compliance")
st.markdown("""
Aplikasi ini melakukan **Otomatisasi Audit Kepatuhan** dengan membandingkan 
SOP IT internal terhadap standar internasional **NIST Cybersecurity Framework 2.0**.
""")

# --- 3. SIDEBAR UNTUK INPUT ---
st.sidebar.header("📂 Data Audit")
nist_file = st.sidebar.file_uploader("Upload Standar NIST CSF 2.0 (PDF)", type="pdf")
sop_file = st.sidebar.file_uploader("Upload SOP IT Kampus (PDF)", type="pdf")

st.sidebar.divider()
st.sidebar.info("Gunakan aplikasi ini untuk mendeteksi gap antara kebijakan internal dan standar global.")

# --- 4. PROSES UTAMA RAG ---
if nist_file and sop_file:
    if st.button("🚀 Jalankan Analisis Audit"):
        with st.spinner("Sedang memproses dokumen dan mencari celah keamanan..."):
            try:
                # Simpan file sementara agar bisa dibaca oleh Loader
                with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp_nist:
                    tmp_nist.write(nist_file.getvalue())
                    nist_path = tmp_nist.name
                
                with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp_sop:
                    tmp_sop.write(sop_file.getvalue())
                    sop_path = tmp_sop.name

                # Load dan Chunking Dokumen
                loaders = [PyPDFLoader(nist_path), PyPDFLoader(sop_path)]
                docs = []
                for loader in loaders:
                    docs.extend(loader.load())

                # Pemisahan teks agar konteks tidak terlalu panjang
                text_splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=150)
                splits = text_splitter.split_documents(docs)

                # Membuat Basis Pengetahuan Vektor (ChromaDB)
                embeddings = HuggingFaceEmbeddings(model_name="sentence-transformers/all-MiniLM-L6-v2")
                vectorstore = Chroma.from_documents(documents=splits, embedding=embeddings)
                retriever = vectorstore.as_retriever(search_kwargs={"k": 5})

                # Inisiasi AI Llama-3.1 melalui Groq
                llm = ChatGroq(model_name="llama-3.1-8b-instant", temperature=0)

                # Prompt Engineering khusus Auditor
                template = """
                Anda adalah Auditor Keamanan Siber yang sangat teliti.
                Tugas: Analisis kesenjangan (Gap Analysis) antara SOP IT Kampus dengan Standar NIST CSF 2.0.
                
                Instruksi:
                1. Temukan 3 poin utama di mana SOP belum memenuhi standar NIST.
                2. Untuk setiap temuan, sebutkan kode Subkategori NIST-nya (misal: GV.OC-01, PR.DS-10).
                3. Berikan saran perbaikan singkat.

                Konteks Dokumen: {context}
                Pertanyaan: {question}
                
                Berikan jawaban dalam Bahasa Indonesia yang profesional.
                """
                prompt = ChatPromptTemplate.from_template(template)

                # RAG Chain
                rag_chain = (
                    {"context": retriever, "question": RunnablePassthrough()}
                    | prompt
                    | llm
                )

                # Eksekusi AI
                response = rag_chain.invoke("Lakukan audit gap analysis")

                # --- 5. TAMPILKAN HASIL ---
                st.success("✅ Analisis Selesai!")
                
                col_text, col_chart = st.columns([2, 1])

                with col_text:
                    st.subheader("📋 Laporan Temuan Audit")
                    st.markdown(response.content)

                with col_chart:
                    st.subheader("📊 Statistik Kepatuhan")
                    # Visualisasi sederhana (Data simulasi untuk prototipe)
                    fokus_nist = ['Govern', 'Identify', 'Protect', 'Detect', 'Respond']
                    skor = [75, 60, 45, 30, 55]
                    
                    fig, ax = plt.subplots()
                    ax.barh(fokus_nist, skor, color='#1f77b4')
                    ax.set_xlim(0, 100)
                    ax.set_xlabel('Persentase Kepatuhan (%)')
                    st.pyplot(fig)

            except Exception as e:
                st.error(f"Terjadi kesalahan teknis: {e}")
else:
    st.warning("⚠️ Mohon upload kedua file PDF di sidebar untuk memulai audit.")

# --- 6. FOOTER ---
st.divider()
st.caption("Aplikasi ini adalah bagian dari Luaran Penelitian Dosen Pemula 2024.")