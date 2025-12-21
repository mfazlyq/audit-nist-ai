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
    if st.button("🚀 Jalankan Analisis Terstruktur"):
        with st.spinner("Menganalisis dan memetakan data ke format Excel NIST..."):
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
                
                # Menambah k=5 agar visualisasi lebih variatif datanya
                retriever = vectorstore.as_retriever(search_kwargs={"k": 5})

                llm = ChatGroq(model_name="llama-3.1-8b-instant", temperature=0)

                template = """
                Anda adalah Auditor Keamanan Siber Senior. Berikan analisis gap dalam format baris per baris.
                Gunakan pemisah " | " untuk setiap kolom.
                
                Wajib sertakan Fungsi NIST (GOVERN, IDENTIFY, PROTECT, DETECT, RESPOND, atau RECOVER) pada kolom kategori.

                Format setiap baris harus:
                Kategori | Subkategori | Current Status | Action Plan
                
                Konteks: {context}
                Tugas: Temukan semua gap antara SOP dan NIST CSF 2.0. Berikan jawaban HANYA dalam format baris-baris tersebut.
                """
                prompt = ChatPromptTemplate.from_template(template)
                rag_chain = ({"context": retriever, "question": RunnablePassthrough()} | prompt | llm)
                
                response = rag_chain.invoke("Lakukan audit gap analysis")
                raw_text = response.content

                # --- 4. LOGIKA PARSING KE DATAFRAME ---
                rows = []
                for line in raw_text.strip().split('\n'):
                    if "|" in line:
                        parts = [p.strip() for p in line.split("|")]
                        if len(parts) >= 4:
                            rows.append(parts[:4])

                df = pd.DataFrame(rows, columns=[
                    "CSF Function/Category", 
                    "Subcategory ID", 
                    "Current Status (Current Profile)", 
                    "Action Plan (Target Profile)"
                ])

                # --- 5. TAMPILKAN HASIL ---
                st.success("✅ Analisis Selesai!")
                
                # Tampilkan Tabel
                st.subheader("📋 Laporan Gap Analysis (NIST Organizational Profile)")
                st.table(df)

                st.divider()

                # --- 6. VISUALISASI STATISTIK (DI BAWAH TABEL) ---
                st.subheader("📊 Statistik Distribusi Gap per Fungsi NIST")
                
                # Standarisasi kategori untuk grafik
                nist_core = ['GOVERN', 'IDENTIFY', 'PROTECT', 'DETECT', 'RESPOND', 'RECOVER']
                
                # Ekstrak fungsi utama dari kolom kategori
                df['Main_Func'] = df['CSF Function/Category'].str.upper().apply(
                    lambda x: next((f for f in nist_core if f in x), 'OTHER')
                )
                
                counts = df['Main_Func'].value_counts().reindex(nist_core, fill_value=0)
                
                # Membuat Grafik
                fig, ax = plt.subplots(figsize=(10, 5))
                colors = ['#4CAF50', '#2196F3', '#FFC107', '#FF5722', '#9C27B0', '#607D8B']
                counts.plot(kind='bar', ax=ax, color=colors)
                
                ax.set_title('Jumlah Temuan Celah Keamanan per Pilar NIST CSF 2.0')
                ax.set_ylabel('Jumlah Gap')
                ax.set_xlabel('Fungsi Utama NIST')
                plt.xticks(rotation=0)
                
                # Tambah label angka di atas batang
                for i, v in enumerate(counts):
                    ax.text(i, v + 0.1, str(int(v)), ha='center', fontweight='bold')
                
                st.pyplot(fig)
                st.info("Grafik di atas menunjukkan pilar mana yang paling banyak memiliki kekurangan dalam SOP IT Kampus Anda.")

                # Export ke Excel
                output = io.BytesIO()
                with pd.ExcelWriter(output, engine='openpyxl') as writer:
                    df.drop(columns=['Main_Func']).to_excel(writer, index=False, sheet_name='NIST_Profile_Report')
                
                st.sidebar.divider()
                st.sidebar.download_button(
                    label="📥 Download Hasil Audit (Excel)",
                    data=output.getvalue(),
                    file_name="NIST_CSF_Audit_Report.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                )

            except Exception as e:
                st.error(f"Error: {e}")