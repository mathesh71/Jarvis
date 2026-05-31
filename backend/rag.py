# rag.py
import os
import pickle
import faiss
import numpy as np
from sentence_transformers import SentenceTransformer
from typing import List
import PyPDF2
import docx

# ---- Config ----
EMBED_MODEL = "all-MiniLM-L6-v2"
EMBED_DIM = 384   # dimension for all-MiniLM-L6-v2
INDEX_PATH = "faiss.index"
DOCS_PATH = "docs.pkl"

# ---- Load embedding model once ----
embed_model = SentenceTransformer(EMBED_MODEL)

# ---- In-memory containers ----
index = None
documents = []        # list of dicts: {'text': chunk_text, 'meta': {...}}
is_index_initialized = False

# ---- Helpers ----
def _ensure_index():
    global index, documents, is_index_initialized
    if index is None:
        if os.path.exists(INDEX_PATH) and os.path.exists(DOCS_PATH):
            # load persisted index + documents
            index = faiss.read_index(INDEX_PATH)
            with open(DOCS_PATH, "rb") as f:
                documents = pickle.load(f)
            print("[RAG] Loaded FAISS index and documents.")
        else:
            # create new index (cosine via inner product + normalized vectors)
            index = faiss.IndexFlatIP(EMBED_DIM)
            documents = []
            print("[RAG] Created new FAISS index.")
    is_index_initialized = True

def _save_index():
    global index, documents
    faiss.write_index(index, INDEX_PATH)
    with open(DOCS_PATH, "wb") as f:
        pickle.dump(documents, f)
    print("[RAG] Saved FAISS index and documents.")

def _embed_texts(texts: List[str]) -> np.ndarray:
    emb = embed_model.encode(texts, show_progress_bar=False, convert_to_numpy=True)
    # normalize for cosine similarity with inner product
    norms = np.linalg.norm(emb, axis=1, keepdims=True)
    norms[norms == 0] = 1e-10
    emb = emb / norms
    return emb.astype("float32")

def chunk_text(text: str, chunk_size: int = 300, overlap: int = 50) -> List[str]:
    words = text.split()
    chunks = []
    i = 0
    while i < len(words):
        chunk = " ".join(words[i:i+chunk_size])
        if chunk.strip():
            chunks.append(chunk.strip())
        i += (chunk_size - overlap)
    return chunks

# ---- Document readers ----
def read_pdf(path: str) -> str:
    text = []
    with open(path, "rb") as f:
        reader = PyPDF2.PdfReader(f)
        for page in reader.pages:
            try:
                text.append(page.extract_text() or "")
            except Exception:
                # skip page on error
                continue
    return "\n".join(text)

def read_docx(path: str) -> str:
    doc = docx.Document(path)
    paragraphs = [p.text for p in doc.paragraphs if p.text]
    return "\n".join(paragraphs)

def read_text(path: str) -> str:
    with open(path, "r", encoding="utf-8", errors="ignore") as f:
        return f.read()

# ---- Public API ----
def load_faiss():
    """Initialize/load the faiss index and documents."""
    _ensure_index()

def add_document_from_file(path: str, meta: dict = None, chunk_size: int = 300, overlap: int = 50) -> int:
    """
    Ingest a file (pdf/docx/txt). Returns number of added chunks.
    meta is arbitrary metadata (e.g., {'source': path}).
    """
    _ensure_index()
    ext = os.path.splitext(path)[1].lower()
    if ext in [".pdf"]:
        text = read_pdf(path)
    elif ext in [".docx"]:
        text = read_docx(path)
    elif ext in [".txt", ".md"]:
        text = read_text(path)
    else:
        raise ValueError("Unsupported file type: " + ext)

    chunks = chunk_text(text, chunk_size=chunk_size, overlap=overlap)
    if not chunks:
        return 0

    embeddings = _embed_texts(chunks)
    # add to FAISS and documents metadata
    index.add(embeddings)
    start_id = len(documents)
    for i, chunk in enumerate(chunks):
        documents.append({"text": chunk, "meta": {"source": path, **(meta or {})}})
    _save_index()
    return len(chunks)

def add_documents_from_folder(folder_path: str, recursive: bool = True):
    """Ingest all supported files from a folder."""
    supported = {".pdf", ".docx", ".txt", ".md"}
    count = 0
    for root, dirs, files in os.walk(folder_path):
        for file in files:
            if os.path.splitext(file)[1].lower() in supported:
                path = os.path.join(root, file)
                try:
                    added = add_document_from_file(path)
                    count += added
                except Exception as e:
                    print("[RAG] Failed to add", path, e)
        if not recursive:
            break
    return count

def search(query: str, top_k: int = 5):
    """Return top_k chunks (texts + meta) relevant to the query."""
    _ensure_index()
    if len(documents) == 0:
        return []

    q_emb = _embed_texts([query])
    D, I = index.search(q_emb, top_k)
    results = []
    for idx in I[0]:
        if idx < len(documents):
            results.append(documents[idx])
    return results

def clear_index():
    """Reset index and remove files."""
    global index, documents
    index = faiss.IndexFlatIP(EMBED_DIM)
    documents = []
    if os.path.exists(INDEX_PATH):
        os.remove(INDEX_PATH)
    if os.path.exists(DOCS_PATH):
        os.remove(DOCS_PATH)
    print("[RAG] Cleared index and documents.")

# ---- higher-level helper that returns prompt-ready context ----
def retrieve_context(query: str, top_k: int = 5) -> str:
    """Return joined context text from top_k results."""
    hits = search(query, top_k)
    parts = []
    for h in hits:
        src = h.get("meta", {}).get("source", "unknown")
        parts.append(f"Source: {src}\n{h['text']}")
    return "\n\n---\n\n".join(parts)
