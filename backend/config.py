from pathlib import Path
import os

ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "backend" / "data"
LOG_DIR = ROOT / "logs"
CORPUS_PATH = DATA_DIR / "pubmed_abstracts.json"
INDEX_DIR = ROOT / "vector_store"
MANIFEST_PATH = INDEX_DIR / "manifest.json"
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "sentence-transformers/all-MiniLM-L6-v2")
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "qwen2.5:3b")
CORS_ORIGINS = [origin.strip() for origin in os.getenv("CORS_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173,http://localhost:5174,http://127.0.0.1:5174").split(",") if origin.strip()]
TOP_K = int(os.getenv("RETRIEVAL_TOP_K", "3"))
MIN_RELEVANCE = float(os.getenv("MIN_RELEVANCE", "0.22"))
