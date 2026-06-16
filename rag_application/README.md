# PDF RAG Chatbot

A Retrieval-Augmented Generation (RAG) application that lets you upload a PDF and ask questions about it using LLMs from Groq or Google Gemini.

---

## How It Works

1. **Upload** a PDF file
2. The app extracts text, splits it into chunks, and converts them into vector embeddings
3. Embeddings are stored in a local ChromaDB vector database
4. When you ask a question, the app finds the most relevant chunks and sends them along with your question to an LLM
5. The LLM answers based only on the content of your PDF

---

## Project Structure

```
rag_application/
├── app.py            # Main Streamlit UI — orchestrates the full pipeline
├── pdf_loader.py     # Extracts text from PDF using PyMuPDF
├── text_splitter.py  # Splits extracted text into overlapping chunks
├── embedder.py       # Converts text chunks into vector embeddings
├── vector_store.py   # Stores and retrieves embeddings using ChromaDB
├── llm_handler.py    # Connects to Groq / Gemini LLM APIs via LangChain
├── rag_chain.py      # Builds the prompt and calls the LLM to get an answer
└── README.md         # This file
```

---

## Setup & Installation

### Prerequisites

- Python 3.11+
- [`uv`](https://docs.astral.sh/uv/) package manager

### 1. Clone the repository

```bash
git clone <your-repo-url>
cd Tutorial
```

### 2. Install dependencies

```bash
uv sync
```

This reads `requirements.txt` and installs all packages into a `.venv` virtual environment automatically.

### 3. Set up environment variables (optional)

Create a `.env` file in the root `Tutorial/` folder:

```
GROQ_API_KEY=your_groq_api_key_here
GEMINI_API_KEY=your_gemini_api_key_here
```

> You can also enter your API key directly in the app's sidebar — no `.env` file is required.

---

## Running the App

```bash
uv run streamlit run rag_application/app.py
```

Then open your browser at: **http://localhost:8501**

---

## Usage

1. In the **sidebar**, select your LLM provider (Groq or Gemini) and model
2. Enter your **API key** for the selected provider
3. Upload a **PDF file** using the file uploader
4. Click **"Process PDF"** and wait for it to complete
5. Type your question in the chat box and press Enter
6. Use **"Clear Chat"** in the sidebar to reset the conversation

---

## Supported LLM Providers

### Groq (Free tier available)
- `qwen/qwen3-32b`
- `llama-3.3-70b-versatile`
- `llama-3.1-8b-instant`

Get a free API key at: https://console.groq.com

### Gemini (Google)
- `gemini-2.5-flash`
- `gemini-2.5-flash-lite`
- `gemini-3.5-flash`

Get an API key at: https://aistudio.google.com

---

## Notes

- Only **normal (text-based) PDFs** are supported. Scanned PDFs require OCR and are not implemented yet.
- The `chroma_db/` folder is auto-generated at runtime and is not committed to the repository.
- The embedding model (`all-MiniLM-L6-v2`) is downloaded automatically on first use and cached locally.
