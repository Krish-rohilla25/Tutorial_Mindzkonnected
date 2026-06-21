import os
import tempfile
import streamlit as st
from dotenv import load_dotenv

from pdf_loader import load_pdf
from text_splitter import split_text
from embedder import get_embedder, embed_chunks
from vector_store import build_vector_store, retrieve_chunks
from llm_handler import get_llm, GROQ_MODELS, GEMINI_MODELS
from rag_chain import get_answer

load_dotenv()

st.set_page_config(page_title="PDF RAG Chatbot", layout="wide")
st.title("PDF RAG Chatbot")
st.write("Upload a PDF, configure your LLM, and start asking questions about it.")


# --- Sidebar: LLM and PDF settings ---

st.sidebar.header("Settings")

provider = st.sidebar.selectbox("LLM Provider", ["Groq", "Gemini"])

if provider == "Groq":
    model_options = GROQ_MODELS
else:
    model_options = GEMINI_MODELS

model_name = st.sidebar.selectbox("Model", model_options)

api_key = st.sidebar.text_input(
    "API Key",
    type="password",
    placeholder=f"Enter your {provider} API key",
)

st.sidebar.markdown("---")

pdf_type = st.sidebar.selectbox("PDF Type", ["Normal PDF", "Scanned PDF"])

if pdf_type == "Scanned PDF":
    st.sidebar.info(
        "Scanned PDF uses OCR to extract text. "
        "Processing may take longer than normal PDFs."
    )

st.sidebar.markdown("---")

if st.sidebar.button("Clear Chat"):
    st.session_state.chat_history = []
    st.rerun()


# --- Session state setup ---

if "chat_history" not in st.session_state:
    st.session_state.chat_history = []

if "collection" not in st.session_state:
    st.session_state.collection = None

if "embedder" not in st.session_state:
    st.session_state.embedder = None

if "pdf_processed" not in st.session_state:
    st.session_state.pdf_processed = False

if "pdf_name" not in st.session_state:
    st.session_state.pdf_name = None


# --- PDF Upload and Processing ---

st.subheader("Upload PDF")

uploaded_file = st.file_uploader("Choose a PDF file", type=["pdf"])

if uploaded_file:
    col1, col2 = st.columns([3, 1])

    with col1:
        st.write(f"File: {uploaded_file.name} ({round(uploaded_file.size / 1024 / 1024, 2)} MB)")

    with col2:
        process_button = st.button("Process PDF")

    if process_button:
        pdf_type_key = "normal" if pdf_type == "Normal PDF" else "scanned"
        spinner_msg = (
            "Reading and processing the PDF... this may take a moment for large files."
            if pdf_type_key == "normal"
            else "Running OCR on scanned PDF... this may take several minutes."
        )

        with st.spinner(spinner_msg):

            # Save uploaded file to a temp file on disk so PyMuPDF can read it
            with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
                tmp.write(uploaded_file.read())
                tmp_path = tmp.name

            raw_text = load_pdf(tmp_path, pdf_type=pdf_type_key)

            chunks = split_text(raw_text)

            # Load embedding model
            if st.session_state.embedder is None:
                st.session_state.embedder = get_embedder()

    
            embeddings = embed_chunks(chunks, st.session_state.embedder)

        
            collection = build_vector_store(chunks, embeddings)

            # Store in session state
            st.session_state.collection = collection
            st.session_state.pdf_processed = True
            st.session_state.pdf_name = uploaded_file.name
            st.session_state.chat_history = []

            # Clean up temp file
            os.unlink(tmp_path)

        st.success(
            f"PDF processed. {len(chunks)} chunks created. You can now ask questions."
        )


# --- Chat Interface ---

if st.session_state.pdf_processed:
    st.markdown("---")
    st.subheader(f"Chat about: {st.session_state.pdf_name}")

    # Display chat history
    for message in st.session_state.chat_history:
        with st.chat_message(message["role"]):
            st.write(message["content"])

    # User input
    user_question = st.chat_input("Ask a question about the PDF...")

    if user_question:
        if not api_key:
            st.error("Please enter your API key in the sidebar before asking questions.")
        else:
            # user message
            with st.chat_message("user"):
                st.write(user_question)

            st.session_state.chat_history.append(
                {"role": "user", "content": user_question}
            )

            with st.chat_message("assistant"):
                with st.spinner("Thinking..."):
                    # Embed the question
                    question_embedding = st.session_state.embedder.encode(user_question)

                    # Retrieve relevant chunks
                    context_chunks = retrieve_chunks(
                        st.session_state.collection, question_embedding, top_k=5
                    )

                    # Get the LLM and generate an answer
                    try:
                        llm = get_llm(provider, model_name, api_key)
                        answer = get_answer(llm, user_question, context_chunks)
                    except Exception as e:
                        answer = f"Error getting answer: {str(e)}"

                    st.write(answer)

            st.session_state.chat_history.append(
                {"role": "assistant", "content": answer}
            )

else:
    st.info("Upload a PDF and click 'Process PDF' to get started.")
