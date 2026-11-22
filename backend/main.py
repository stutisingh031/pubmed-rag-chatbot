import logging
import time
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
import requests
from .logging_config import configure_logging, new_request_id, request_id_var
from .config import CORPUS_PATH, CORS_ORIGINS, OLLAMA_BASE_URL, OLLAMA_MODEL

configure_logging()
logger = logging.getLogger(__name__)
from .rag import ResearchRAG
rag = ResearchRAG()

@asynccontextmanager
async def lifespan(app):
    logger.info("Application started")
    yield
    logger.info("Application stopped")

app = FastAPI(title="Gene-Trait Research Assistant", version="1.0.0", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=CORS_ORIGINS, allow_methods=["GET","POST"], allow_headers=["*"])

@app.middleware("http")
async def request_logging(request: Request, call_next):
    rid = request.headers.get("X-Request-ID") or new_request_id()
    token = request_id_var.set(rid)
    started = time.perf_counter()
    try:
        response = await call_next(request)
        response.headers["X-Request-ID"] = rid
        logger.info("%s %s status=%s duration_ms=%.1f", request.method, request.url.path, response.status_code, (time.perf_counter()-started)*1000)
        return response
    except Exception:
        logger.exception("Unhandled request failure")
        raise
    finally:
        request_id_var.reset(token)

class ChatRequest(BaseModel):
    question: str = Field(min_length=3, max_length=2000)

@app.get("/api/health")
def health():
    ollama = ollama_health()
    ready = rag.store is not None and rag.llm is not None and ollama["available"]
    return {"status":"ok" if ready else "degraded","ready":ready,"index_error":rag.index_error,"ollama":ollama}

def ollama_health():
    try:
        response = requests.get(f"{OLLAMA_BASE_URL.rstrip('/')}/api/tags",timeout=1.5)
        response.raise_for_status()
        models = [item.get("name","") for item in response.json().get("models",[])]
        alias_match = OLLAMA_MODEL.endswith(":latest") and any(name.split(":")[0] == OLLAMA_MODEL.split(":")[0] for name in models)
        available = OLLAMA_MODEL in models or alias_match
        return {"available":available,"model":OLLAMA_MODEL,"error":None if available else "Configured Ollama model is not installed."}
    except requests.RequestException as exc:
        return {"available":False,"model":OLLAMA_MODEL,"error":str(exc)}

@app.get("/api/corpus")
def corpus_summary():
    if not CORPUS_PATH.exists():
        return {"count":0,"records":[]}
    import json
    records = json.loads(CORPUS_PATH.read_text(encoding="utf-8"))["records"]
    return {"count":len(records),"records":[{"pmid":r["pmid"],"title":r["title"],"year":r["publication_year"],"source_url":r["source_url"]} for r in records]}

@app.post("/api/chat")
def chat(body: ChatRequest):
    started = time.perf_counter()
    if not rag.store or not rag.llm:
        raise HTTPException(status_code=503, detail={"message":"Research assistant is not ready.","reason":rag.index_error})
    try:
        result = rag.answer(body.question)
        logger.info("chat status=%s retrieved=%s citations=%s duration_ms=%.1f",result["status"],len(result["evidence"]),len(result["citations"]),(time.perf_counter()-started)*1000)
        return result
    except Exception as exc:
        logger.exception("Question answering failed")
        raise HTTPException(status_code=502, detail="Local generation failed; please check Ollama and application logs.") from exc
