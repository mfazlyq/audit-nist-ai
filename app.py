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

# --- 1. SETUP API & PAGE ---
if "GROQ_API_KEY" in st.secrets:
    os.environ["GROQ_API_KEY"] = st.secrets["GROQ_API_KEY"]

st.set_page_config(page_title="AI Cyber-Auditor NIST CSF 2.0", layout="wide")
st.title("🛡️ AI Cyber-Auditor: NIST CSF 2.0 Dashboard")

# --- 2. SIDEBAR ---
st.sidebar.header("📂 Upload Dokumen")
nist_file = st.sidebar.file_uploader("Standar NIST CSF 2.0 (PDF)", type="pdf")
sop_file = st.sidebar.file_uploader("SOP IT Kampus (PDF)", type="pdf")

# --- 3. LOGIKA ANALISIS ---
if nist_file and sop_file:
    if st.button("🚀 Mulai Audit & Visualisasi"):
        with st.spinner("Menganalisis celah keamanan berdasarkan 6 Fungsi NIST..."):
            try:
                # Proses Dokumen
                with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as t1: t1.write(nist_file.read()); n_p = t1.name
                with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as t2: t2.write(sop_file.read()); s_p = t2.name

                docs = []
                for p in [n_p, s_p]: docs.extend(PyPDFLoader(p).load())
                splits = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=150).split_documents(docs)
                
                v_store = Chroma.from_documents(documents=splits, embedding=HuggingFaceEmbeddings(model_name="sentence-transformers/all-MiniLM-L6-v2"))
                retriever = v_store.as_retriever(search_kwargs={"k": 5})

                # Prompt Khusus untuk Pemetaan Fungsi
                template = """
                Anda adalah Auditor Senior. Temukan gap antara SOP dan NIST CSF 2.0.
                Wajib sertakan Fungsi NIST (GOVERN, IDENTIFY, PROTECT, DETECT, RESPOND, atau RECOVER) di awal setiap temuan.

                Format per baris: Fungsi | Subkategori | Status Saat Ini | Rencana Aksi
                Tugas: Berikan minimal 10 temuan gap. HANYA format tersebut.
                
                Konteks: {context}
                """
                llm = ChatGroq(model_name="llama-3.1-8b-instant", temperature=0)
                chain = ({"context": retriever, "question": RunnablePassthrough()} | ChatPromptTemplate.from_template(template) | llm)
                
                res = chain.invoke("Lakukan audit").content

                # Parsing ke Tabel
                rows = [line.split("|") for line in res.strip().split('\n') if "|" in line]
                df = pd.DataFrame(rows, columns=["Fungsi", "ID", "Current Status", "Action Plan"])
                df = df.apply(lambda x: x.str.strip())

                # --- 4. VISUALISASI BERDASARKAN FUNGSI NIST ---
                st.success("✅ Audit Selesai!")
                c1, c2 = st.columns([2, 1])

                with c1:
                    st.subheader("📋 Tabel Temuan Gap Analysis")
                    st.dataframe(df, use_container_width=True)

                with c2:
                    st.subheader("📊 Statistik per Fungsi NIST")
                    
                    # Logika: Memastikan hanya 6 Fungsi NIST yang dihitung
                    nist_functions = ['GOVERN', 'IDENTIFY', 'PROTECT', 'DETECT', 'RESPOND', 'RECOVER']
                    df['Fungsi_Clean'] = df['Fungsi'].str.upper().apply(lambda x: next((f for f in nist_functions if f in x), 'LAINNYA'))
                    
                    counts = df['Fungsi_Clean'].value_counts().reindex(nist_functions, fill_value=0)
                    
                    fig, ax = plt.subplots(figsize=(5, 4))
                    colors = ['#4CAF50', '#2196F3', '#FFC107', '#FF5722', '#9C27B0', '#607D8B']
                    counts.plot(kind='bar', ax=ax, color=colors)
                    ax.set_ylabel('Jumlah Temuan Gap')
                    plt.xticks(rotation=45)
                    st.pyplot(fig)
                    st.caption("Grafik ini menunjukkan distribusi kelemahan SOP berdasarkan pilar NIST CSF 2.0.")

                # Export Excel
                out = io.BytesIO()
                with pd.ExcelWriter(out, engine='openpyxl') as w: df.to_excel(w, index=False)
                st.sidebar.download_button("📥 Download Laporan Excel", out.getvalue(), "Audit_NIST_Report.xlsx")

            except Exception as e:
                st.error(f"Kesalahan: {e}")