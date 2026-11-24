"""
rag/ingest.py
Ingests the inventory policy document into ChromaDB
using NVIDIA NeMo Retriever embeddings.

Run after setup_db.py:
  python rag/ingest.py

Requires:
  NVIDIA_API_KEY in .env or environment
"""

import os
import sys
import re
from pathlib import Path
from typing import List

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

from dotenv import load_dotenv
load_dotenv()

NVIDIA_API_KEY = os.environ.get("NVIDIA_API_KEY", "")
POLICY_DIR     = Path("policy")
CHROMA_DIR     = Path("db/chroma")
COLLECTION     = "inventory_policy"

EMBED_MODEL    = "nvidia/nemotron-3-embed-1b"
EMBED_BASE_URL = "https://integrate.api.nvidia.com/v1"

CHUNK_SIZE     = 400   # characters
CHUNK_OVERLAP  = 80


# ── NeMo Retriever embedding function ─────────────────────────────────────────

class NeMoEmbeddingFunction:
    """
    ChromaDB-compatible embedding function using NVIDIA NeMo Retriever.
    Falls back to a simple TF-IDF hash if API key is not set (for testing).
    """

    def name(self) -> str:          # required by ChromaDB >= 1.0
        return "nemo-retriever-embedding"

    def __init__(self):
        self._use_fallback = False
        if not NVIDIA_API_KEY:
            print("⚠️  NVIDIA_API_KEY not set — using fallback embeddings.")
            print("   Set it in .env to use NeMo Retriever.")
            self._use_fallback = True
        else:
            from openai import OpenAI
            try:
                self._client = OpenAI(
                    base_url=EMBED_BASE_URL,
                    api_key=NVIDIA_API_KEY,
                )
            except TypeError as e:
                if "proxies" in str(e):
                    raise RuntimeError(
                        "OpenAI/httpx version mismatch detected. "
                        "Run: pip install \"httpx<0.28\" or reinstall requirements.txt."
                    ) from e
                raise
    def __call__(self, input: List[str]) -> List[List[float]]:
        if self._use_fallback:
            return self._fallback_embed(input)
        try:
            return self._nemo_embed(input)
        except Exception as e:
            print(f"⚠️  NeMo embedding request failed ({e}).")
            print("   Falling back to local deterministic embeddings for this run.")
            self._use_fallback = True
            return self._fallback_embed(input)

    def _nemo_embed(self, texts: List[str]) -> List[List[float]]:
        embeddings = []
        # NeMo API accepts up to 96 texts per call; batch to be safe
        for text in texts:
            resp = self._client.embeddings.create(
                input=[text],
                model=EMBED_MODEL,
                encoding_format="float",
                extra_body={"input_type": "passage", "truncate": "END"},
            )
            embeddings.append(resp.data[0].embedding)
        return embeddings

    def _fallback_embed(self, texts: List[str]) -> List[List[float]]:
        """Deterministic 384-dim pseudo-embedding for offline testing."""
        import hashlib, math
        results = []
        for text in texts:
            vec = []
            for i in range(384):
                h = hashlib.md5(f"{text}{i}".encode()).hexdigest()
                vec.append((int(h, 16) % 10000 - 5000) / 5000.0)
            norm = math.sqrt(sum(x**2 for x in vec)) or 1.0
            results.append([x / norm for x in vec])
        return results


# ── Text chunking ─────────────────────────────────────────────────────────────

def chunk_text(text: str, size: int = CHUNK_SIZE, overlap: int = CHUNK_OVERLAP) -> List[str]:
    """Split text into overlapping chunks, preserving sentence boundaries."""
    # Split on sentence-ending punctuation
    sentences = re.split(r'(?<=[.!?])\s+', text)
    chunks, current = [], ""

    for sentence in sentences:
        if len(current) + len(sentence) + 1 <= size:
            current = (current + " " + sentence).strip()
        else:
            if current:
                chunks.append(current)
            # Start new chunk with overlap from the end of the last chunk
            if len(current) > overlap:
                current = current[-overlap:] + " " + sentence
            else:
                current = sentence

    if current:
        chunks.append(current)

    return [c for c in chunks if len(c.strip()) > 20]


def load_policy_documents() -> List[dict]:
    """Load all .txt and .pdf files from the policy directory."""
    docs = []

    for path in POLICY_DIR.iterdir():
        if path.suffix == '.txt':
            text = path.read_text(encoding='utf-8')
            docs.append({'filename': path.name, 'text': text})

        elif path.suffix == '.pdf':
            try:
                import pypdf
                reader = pypdf.PdfReader(str(path))
                text = "\n".join(page.extract_text() or "" for page in reader.pages)
                docs.append({'filename': path.name, 'text': text})
            except ImportError:
                print(f"⚠️  pypdf not installed — skipping {path.name}")

    return docs


# ── Main ingest pipeline ──────────────────────────────────────────────────────

def main():
    import chromadb
    from chromadb.config import Settings

    print("📄  Loading policy documents...")
    docs = load_policy_documents()
    if not docs:
        print(f"❌  No documents found in {POLICY_DIR}/")
        sys.exit(1)

    print(f"    Found {len(docs)} document(s)")

    # Chunk all documents
    all_chunks, all_ids, all_metadata = [], [], []
    for doc in docs:
        chunks = chunk_text(doc['text'])
        print(f"    {doc['filename']} → {len(chunks)} chunks")
        for j, chunk in enumerate(chunks):
            all_chunks.append(chunk)
            all_ids.append(f"{doc['filename']}__chunk{j:04d}")
            all_metadata.append({'source': doc['filename'], 'chunk_idx': j})

    print(f"\n🔢  Embedding {len(all_chunks)} chunks via NVIDIA NeMo Retriever...")
    embed_fn = NeMoEmbeddingFunction()

    CHROMA_DIR.mkdir(parents=True, exist_ok=True)
    client = chromadb.PersistentClient(
        path=str(CHROMA_DIR),
        settings=Settings(anonymized_telemetry=False),
    )

    # Delete existing collection if it exists
    try:
        client.delete_collection(COLLECTION)
    except Exception:
        pass

    collection = client.create_collection(
        name=COLLECTION,
        embedding_function=embed_fn,  # type: ignore
        metadata={"hnsw:space": "cosine"},
    )

    # Add in batches of 50
    batch = 50
    for start in range(0, len(all_chunks), batch):
        end = min(start + batch, len(all_chunks))
        collection.add(
            documents=all_chunks[start:end],
            ids=all_ids[start:end],
            metadatas=all_metadata[start:end],
        )
        print(f"    Indexed chunks {start+1}–{end} / {len(all_chunks)}")

    print(f"\n✅  ChromaDB ready: {CHROMA_DIR}/")
    print(f"    Collection: '{COLLECTION}'")
    print(f"    Documents indexed: {collection.count()}")
    print(f"\nNext: streamlit run app.py")


if __name__ == '__main__':
    main()
