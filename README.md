# InventoryIQ

InventoryIQ is an NVIDIA-powered inventory policy assistant and operational command center. It combines inventory analytics, GPU anomaly scoring, policy retrieval, and policy-grounded AI explanations in one web application.

## What it includes

- React + Vite frontend with command center, inventory explorer, supplier pulse, and policy copilot views.
- FastAPI backend with inventory, supplier, health, insight, and policy endpoints.
- SQLite operational database generated from the included inventory data.
- NVIDIA RAPIDS cuML anomaly-scoring notebook for Google Colab.
- NVIDIA NeMo Retriever + ChromaDB policy retrieval.
- NVIDIA NIM explanations and policy Q&A with offline fallback responses.

## Project layout

```text
analytics/     Compliance, drift, and SLOB metrics
backend/       FastAPI service
data/          Reproducible input CSVs and data preparation scripts
docs/          Demo and project handoff material
frontend/      React/Vite user interface
notebooks/     RAPIDS cuML Colab notebook
policy/        Inventory policy source document
rag/           Policy ingestion and RAG chain
tools/         Supporting document/build utilities
app.py         Legacy Streamlit dashboard
setup_db.py    Builds db/inventoryiq.db from data files
```

Generated databases, vector indexes, caches, build output, temporary files, secrets, and dependency folders are intentionally excluded from this upload folder. They are recreated locally by the setup steps below.

## Setup

### Backend

Python 3.10+ is recommended.

```bash
python -m venv .venv
# Windows: .venv\\Scripts\\activate
# macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
copy .env.example .env  # Windows
# cp .env.example .env  # macOS/Linux
```

Add an NVIDIA API key to `.env` if you want live NIM and NeMo services. Never commit `.env`.

Build the local operational database:

```bash
python setup_db.py
```

Start the API:

```bash
uvicorn backend.main:app --reload --port 8000
```

### Policy retrieval

```bash
python rag/ingest.py
```

This creates the ignored `db/chroma/` index locally.

### Frontend

In a second terminal:

```bash
cd frontend
npm install
npm run dev
```

Open `http://127.0.0.1:5173`.

## Demo data

The included dataset contains 500 synthetic SKUs. The current prototype reports below-ROP items, slow-moving and obsolete stock, supplier lead-time drift, compliance scores, and value at risk. Replace the CSV inputs with approved operational data before any production use.

## NVIDIA components

| Component | Role |
|---|---|
| RAPIDS cuML | GPU anomaly scoring for slow-moving and obsolete stock |
| NeMo Retriever | Policy embeddings and retrieval through ChromaDB |
| NVIDIA NIM | Policy-grounded explanations and natural-language answers |

## Security notes

- Keep NVIDIA credentials in `.env` or deployment secrets.
- Do not commit local databases, Chroma indexes, `node_modules`, or generated reports.
- Review CORS and authentication settings before production deployment.
