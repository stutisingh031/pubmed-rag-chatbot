# Gene–Trait Research Assistant

A local-first, evidence-grounded literature chatbot for the relationship between **BRCA1 and breast cancer susceptibility**. It retrieves verified PubMed abstracts, answers from retrieved text, and only returns citations whose PMIDs occur in that evidence. It is a research prototype, not a clinical decision tool.

## Repository layout

```text
backend/
  data/pmids.json              # 20 PMID candidates; one replaced after live verification
  data/pubmed_abstracts.json   # E-utilities source of truth (full returned abstracts)
  pubmed.py                   # EFetch, parse, validate and save
  rag.py                      # LangChain, Hugging Face, FAISS and Ollama
  main.py                     # FastAPI endpoints and request logging
  evaluate.py                 # Seven-case runner and custom metrics
  requirements.txt
evaluation/
  golden_cases.json           # exactly five answerable, two unanswerable
  results.json                # written by evaluation run
frontend/                      # independent React/Vite application
  src/
  .env.example                # FastAPI base URL; no API key
  package.json
tests/                         # parser, corpus, evaluation checks
logs/app.log                   # rotating application log
vector_store/                  # generated persistent FAISS index and manifest
design_note.md
```

## Prerequisites

- Python 3.11 or newer
- Node.js 20 or newer
- Ollama installed locally, with `qwen2.5:3b` pulled
- Network access for the initial PubMed fetch and first Hugging Face model download

No hosted model API, database, or vector service is used. The local embedding model runs on CPU by default; set `EMBEDDING_MODEL`, `OLLAMA_MODEL`, `OLLAMA_BASE_URL`, `RETRIEVAL_TOP_K`, or `MIN_RELEVANCE` to override defaults.

## Setup and run

The backend and frontend are separate projects. Start each from its own directory/command in separate terminals.

### Backend

From the repository root, create and activate a virtual environment, then install backend dependencies:

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r backend\requirements.txt
```

Fetch and validate the 20 candidate records using NCBI E-utilities. The manifest in the source pack is not treated as final metadata. A candidate with an unrelated abstract was excluded and replaced after verification. The script deduplicates by PMID and excludes records without a title or abstract.

```powershell
python -m backend.pubmed
python -m backend.rag --build
```

The first build downloads `sentence-transformers/all-MiniLM-L6-v2`, embeds one abstract per LangChain document and writes `vector_store/`. Rebuild after a corpus or embedding model change. At query time the index is loaded from disk; it is not silently rebuilt.

Pull and start the local generator, in a separate terminal:

```powershell
ollama pull qwen2.5:3b
ollama serve
```

Start FastAPI in another terminal:

```powershell
python -m uvicorn backend.main:app --host 127.0.0.1 --port 8000
```

Start the React app from the frontend directory:

```powershell
Set-Location frontend
Copy-Item .env.example .env
npm install
npm run dev
```

Open the Vite URL printed by the command (normally `http://localhost:5173`). `frontend/.env` sets `VITE_API_URL=http://127.0.0.1:8000`, which connects React to FastAPI. This is a local endpoint setting; no API key is required. The backend exposes `GET /api/health`, `GET /api/corpus`, and `POST /api/chat` with JSON `{ "question": "..." }`. If Vite chooses a different port, add that origin to the backend's `CORS_ORIGINS` environment variable.

## Evaluation and tests

The seven cases were written after inspecting the fetched abstracts. Run all seven through the same retrieval and generation path, save per-case answers/retrieved PMIDs and custom metrics, then separately attempt RAGAS on the five answerable items:

```powershell
python -m backend.evaluate
python -m backend.evaluate --ragas
python -m pytest -q
```

The custom report covers answerable success, unanswerable refusal accuracy, overall refusal accuracy, citation validity, expected PMID retrieval, false-positive abstention and false-negative abstention. RAGAS answer similarity uses the local embedding model and does not measure refusal quality. A RAGAS faithfulness run with local Qwen was tested but timed out on this CPU-only host, so the runnable RAGAS path reports answer similarity only. The similarity attempt also failed to finish during verification. Run `python -m backend.evaluate --ragas-only` to retry it from saved outputs; `evaluation/results.json` records measured metrics or the actual failure status and never fills in expected scores.

## Evidence and safety behavior

- Abstracts retain PMID, title, authors, journal, publication year, source, and PubMed URL in JSON and in LangChain metadata.
- FAISS is local and persistent. A SHA-256 corpus manifest prevents stale indexes from being used silently.
- The prompt requires evidence-only answers and citations. The backend drops any response with an unsupported PMID, and abstains when the model abstains or returns no verifiable citation.
- Retrieval similarity is only a relevance signal; it is not proof that a claim is supported. This remains a small-corpus prototype, and review of generated answers is appropriate.
- Logs use console plus `RotatingFileHandler`; request IDs, durations, retrieval counts, citation counts, errors, and corpus/index operations are recorded. Prompts and full abstracts are not logged.

## Limitations

The source set is small, abstract-only, and heterogeneous in publication date and study design. It cannot provide individualized risk or clinical recommendations, and the abstracts may omit important methods and caveats. Qwen2.5 3B may fail to follow the evidence prompt consistently; citation checks and abstention reduce but do not eliminate unsupported reasoning. The RAGAS judge is local and model-based, so its output is not independent ground truth. Initial setup requires internet access to NCBI and Hugging Face; inference is local after the model and index are available.
