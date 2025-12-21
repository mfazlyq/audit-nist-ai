import streamlit as st
import os
import tempfile
import pandas as pd
import io
import matplotlib.pyplot as plt
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

# --- 2. SIDEBAR ---
st.sidebar.header("📂 Data Audit")
nist_file = st.sidebar.file_uploader("Upload Standar NIST CSF 2.0 (PDF)", type="pdf")
sop_file = st.sidebar.file_uploader("Upload SOP IT Kampus (PDF)", type="pdf")

# --- 3. PROSES UTAMA ---
if nist_file and sop_file:
    if st.button("🚀 Jalankan Analisis Lengkap"):
        with st.spinner("Sedang memproses dokumen dan membuat visualisasi..."):
            try:
                # Ingestion
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
                retriever = vectorstore.as_retriever(search_kwargs={"k": 4}) # k=4 untuk keseimbangan detail & token

                llm = ChatGroq(model_name="llama-3.1-8b-instant", temperature=0)

                # Prompt Terstruktur untuk Tabel NIST
                template = """
                Anda adalah Auditor Keamanan Siber Senior. Berikan analisis gap dalam format baris per baris.
                Gunakan pemisah " | " untuk setiap kolom.
                
                Format setiap baris harus:
                Kategori | Subkategori | Current Status | Action Plan
                
                Konteks: {context}
                Tugas: Temukan minimal 10 gap utama antara SOP dan NIST CSF 2.0. Berikan jawaban HANYA dalam format baris tersebut.
                """
                prompt = ChatPromptTemplate.from_template(template)
                rag_chain = ({"context": retriever, "question": RunnablePassthrough()} | prompt | llm)
                
                response = rag_chain.invoke("Lakukan audit gap analysis")
                raw_text = response.content

                # Parsing ke DataFrame
                rows = []
                for line in raw_text.strip().split('\n'):
                    if "|" in line:
                        parts = [p.strip() for p in line.split("|")]
                        if len(parts) >= 4: rows.append(parts[:4])

                df = pd.DataFrame(rows, columns=["Function/Category", "Subcategory ID", "Current Status", "Action Plan"])

                # --- 4. TAMPILKAN HASIL DENGAN LAYOUT KOLOM ---
                st.success("✅ Analisis Selesai!")
                
                col_table, col_viz = st.columns([2, 1])

                with col_table:
                    st.subheader("📋 Laporan Organizational Profile")
                    st.dataframe(df, use_container_width=True)

                with col_viz:
                    st.subheader("📊 Distribusi Temuan Gap")
                    # Visualisasi: Menghitung berapa banyak temuan per Fungsi NIST
                    # Kita ambil kata pertama dari kolom Kategori (GOVERN, PROTECT, dll)
                    df['Main_Func'] = df['Function/Category'].str.split().str[0].str.upper()
                    count_data = df['Main_Func'].value_counts()
                    
                    fig, ax = plt.subplots()
                    count_data.plot(kind='barh', ax=ax, color='#1f77b4')
                    ax.set_xlabel('Jumlah Temuan Gap')
                    ax.invert_yaxis() # Biar urutannya enak dibaca
                    st.pyplot(fig)
                    
                    st.info("Grafik ini menunjukkan area mana yang paling banyak memiliki celah keamanan (gap) di kampus Anda.")

                # --- 5. EXPORT EXCEL ---
                output = io.BytesIO()
                with pd.ExcelWriter(output, engine='openpyxl') as writer:
                    df.drop(columns=['Main_Func']).to_excel(writer, index=False, sheet_name='NIST_Audit')
                
                st.sidebar.divider()
                st.sidebar.download_button(
                    label="📥 Download Hasil (Excel)",
                    data=output.getvalue(),
                    file_name="Audit_NIST_SOP_Kampus.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                )

            except Exception as e:
                st.error(f"Terjadi kesalahan: {e}")