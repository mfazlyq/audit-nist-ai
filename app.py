import streamlit as st
import os
import tempfile
import pandas as pd
import io
import re
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
    # Untuk pengujian lokal
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
                
                # Menggunakan k=5 agar data visualisasi lebih kaya
                retriever = vectorstore.as_retriever(search_kwargs={"k": 5})

                llm = ChatGroq(model_name="llama-3.1-8b-instant", temperature=0)

                # PROMPT ANDA (Dipertahankan sesuai permintaan)
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

                # --- 4. LOGIKA PARSING DATA ---
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

                # --- 5. TAMPILKAN TABEL HASIL ---
                st.success("✅ Analisis Selesai!")
                st.subheader("📋 Tabel Temuan Gap Analysis (NIST Profile)")
                st.table(df)

                st.divider()

                # --- 6. LAPORAN SINGKAT (SUMMARY) ---
                st.subheader("📝 Ringkasan Eksekutif (Summary)")
                total_gap = len(df)
                
                # Logika ekstraksi fungsi untuk statistik
                nist_core = ['GOVERN', 'IDENTIFY', 'PROTECT', 'DETECT', 'RESPOND', 'RECOVER']
                # Mencari kata kunci NIST di kolom pertama (Case-Insensitive)
                df['Main_Func'] = df['CSF Function/Category'].str.upper().apply(
                    lambda x: next((f for f in nist_core if f in x), 'OTHER')
                )
                counts = df['Main_Func'].value_counts()
                top_issue = counts.idxmax() if not counts.empty and counts.idxmax() != 'OTHER' else "N/A"

                # Penulisan summary yang aman dari SyntaxError
                summary_text = (
                    f"Berdasarkan analisis audit otomatis terhadap dokumen Anda:\n\n"
                    f"- **Total Temuan Gap**: Telah teridentifikasi {total_gap} celah keamanan.\n"
                    f"- **Area Prioritas Utama**: Fungsi **{top_issue}** memiliki temuan terbanyak yang perlu segera ditinjau.\n"
                    f"- **Rekomendasi**: Segera lakukan pembaruan SOP pada poin-poin yang tercantum di kolom Action Plan."
                )
                st.info(summary_text)

                # --- 7. VISUALISASI STATISTIK (DI BAWAH TABEL) ---
                st.subheader("📊 Statistik Distribusi Gap per Fungsi NIST")
                
                # Memastikan urutan grafik sesuai standar NIST
                plot_data = counts.reindex(nist_core, fill_value=0)
                
                fig, ax = plt.subplots(figsize=(10, 5))
                colors = ['#4CAF50', '#2196F3', '#FFC107', '#FF5722', '#9C27B0', '#607D8B']
                plot_data.plot(kind='bar', ax=ax, color=colors)
                
                ax.set_title('Frekuensi Gap per Pilar NIST CSF 2.0')
                ax.set_ylabel('Jumlah Temuan')
                ax.set_xlabel('Fungsi Utama NIST')
                plt.xticks(rotation=0)
                
                # Label angka di atas batang
                for i, v in enumerate(plot_data):
                    ax.text(i, v + 0.1, str(int(v)), ha='center', fontweight='bold')
                
                st.pyplot(fig)

                # --- 8. EXPORT EXCEL ---
                output = io.BytesIO()
                with pd.ExcelWriter(output, engine='openpyxl') as writer:
                    df.drop(columns=['Main_Func']).to_excel(writer, index=False, sheet_name='NIST_Profile_Report')
                
                st.sidebar.divider()
                st.sidebar.subheader("📥 Download")
                st.sidebar.download_button(
                    label="Download Laporan Excel",
                    data=output.getvalue(),
                    file_name="NIST_CSF_Audit_Report.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                )

            except Exception as e:
                st.error(f"Terjadi kesalahan teknis: {e}")
else:
    st.warning("⚠️ Silakan upload file PDF Standar NIST dan SOP Kampus di sidebar.")

st.divider()
st.caption("Prototipe AI Cyber-Auditor NIST CSF 2.0 - 2024")