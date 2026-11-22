"""LangChain + local embedding + persistent FAISS retrieval and Ollama generation."""
import hashlib
import json
import logging
from pathlib import Path
from typing import Any
import numpy as np
import re
from .config import CORPUS_PATH, EMBEDDING_MODEL, INDEX_DIR, MANIFEST_PATH, MIN_RELEVANCE, OLLAMA_BASE_URL, OLLAMA_MODEL, TOP_K

logger = logging.getLogger(__name__)

def user_facing_refusal(question: str, reason: str) -> str:
    text = question.lower()
    clinical_terms = ("screening", "mammogram", "treatment", "medication", "diagnos", "my risk", "my chance", "should i", "what should i", "personal risk")
    if any(term in text for term in clinical_terms):
        return ("These PubMed abstracts can’t provide personal screening, diagnosis, or treatment guidance. "
                "I can summarize research findings about BRCA1 and breast cancer susceptibility; for decisions about your care, please consult a qualified healthcare professional.")
    if "No sufficiently relevant abstracts" in reason:
        return ("That’s outside the scope of this assistant. It answers questions about BRCA1 and breast cancer susceptibility using indexed PubMed abstracts. "
                "Try asking about inherited BRCA1 variants, DNA repair, or a finding from a specific study.")
    return ("I found related PubMed abstracts, but they don’t provide enough evidence to answer that specific question. "
            "You could ask about BRCA1 variants, DNA repair, or a breast cancer susceptibility finding reported in a study.")

def response_is_abstention(response: str) -> bool:
    text = response.strip().lower()
    return text == "abstain" or "[abstain]" in text or any(phrase in text for phrase in (
        "i can't answer", "i cannot answer", "must abstain", "not explicitly stated in the provided evidence",
        "not stated in the provided evidence", "not present in the evidence", "insufficient evidence to answer"
    ))

def dependencies():
    from langchain_core.documents import Document
    from langchain_huggingface import HuggingFaceEmbeddings
    from langchain_community.vectorstores import FAISS
    from langchain_ollama import ChatOllama
    return Document, HuggingFaceEmbeddings, FAISS, ChatOllama

def corpus_payload():
    return json.loads(CORPUS_PATH.read_text(encoding="utf-8"))

def save_faiss_store(store):
    """Persist FAISS bytes via Python file handles (works in Unicode Windows paths)."""
    import faiss
    INDEX_DIR.mkdir(parents=True, exist_ok=True)
    (INDEX_DIR / "index.faiss").write_bytes(faiss.serialize_index(store.index).tobytes())
    items = []
    for index, doc_id in sorted(store.index_to_docstore_id.items()):
        doc = store.docstore.search(doc_id)
        items.append({"index":index,"id":doc_id,"page_content":doc.page_content,"metadata":doc.metadata})
    (INDEX_DIR / "documents.json").write_text(json.dumps(items,ensure_ascii=False),encoding="utf-8")

def load_faiss_store(embeddings, FAISS, Document):
    import faiss
    from langchain_community.docstore.in_memory import InMemoryDocstore
    index = faiss.deserialize_index(np.frombuffer((INDEX_DIR / "index.faiss").read_bytes(),dtype=np.uint8))
    items = json.loads((INDEX_DIR / "documents.json").read_text(encoding="utf-8"))
    docs = {item["id"]:Document(page_content=item["page_content"],metadata=item["metadata"]) for item in items}
    mapping = {item["index"]:item["id"] for item in items}
    return FAISS(embedding_function=embeddings,index=index,docstore=InMemoryDocstore(docs),index_to_docstore_id=mapping)

def build_index():
    Document, HuggingFaceEmbeddings, FAISS, _ = dependencies()
    data = corpus_payload()
    records = data["records"]
    if len({r["pmid"] for r in records}) != len(records):
        raise ValueError("Corpus contains duplicate PMIDs")
    docs = [Document(page_content=r["abstract"], metadata={k:r[k] for k in ("pmid","title","authors","journal","publication_year","source","source_url")}) for r in records]
    embeddings = HuggingFaceEmbeddings(model_name=EMBEDDING_MODEL, model_kwargs={"device":"cpu"}, encode_kwargs={"normalize_embeddings":True})
    store = FAISS.from_documents(docs, embeddings)
    save_faiss_store(store)
    checksum = hashlib.sha256(CORPUS_PATH.read_bytes()).hexdigest()
    MANIFEST_PATH.write_text(json.dumps({"corpus_sha256":checksum,"embedding_model":EMBEDDING_MODEL,"document_count":len(docs)}, indent=2), encoding="utf-8")
    logger.info("Built persistent FAISS index for %d abstracts", len(docs))
    return len(docs)

class ResearchRAG:
    def __init__(self):
        self.store = None
        self.embeddings = None
        self.llm = None
        self.index_error = None
        try:
            if not MANIFEST_PATH.exists() or not CORPUS_PATH.exists():
                raise FileNotFoundError("Corpus/index missing. Run python -m backend.pubmed then python -m backend.rag --build")
            manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
            if hashlib.sha256(CORPUS_PATH.read_bytes()).hexdigest() != manifest["corpus_sha256"]:
                raise RuntimeError("Corpus changed since FAISS build; rebuild the index")
            Document, HuggingFaceEmbeddings, FAISS, ChatOllama = dependencies()
            self.embeddings = HuggingFaceEmbeddings(model_name=EMBEDDING_MODEL, model_kwargs={"device":"cpu"}, encode_kwargs={"normalize_embeddings":True})
            self.store = load_faiss_store(self.embeddings,FAISS,Document)
            self.llm = ChatOllama(model=OLLAMA_MODEL, base_url=OLLAMA_BASE_URL, temperature=0, num_predict=128)
        except Exception as e:
            self.index_error = str(e)
            logger.exception("RAG initialization failed")

    def answer(self, question: str) -> dict[str, Any]:
        if not self.store or not self.llm:
            raise RuntimeError(self.index_error or "RAG components unavailable")
        hits = self.store.similarity_search_with_relevance_scores(question, k=TOP_K)
        evidence = [(doc, score) for doc, score in hits if score >= MIN_RELEVANCE]
        if not evidence:
            reason = "No sufficiently relevant abstracts were retrieved."
            return {"status":"abstained","answer":user_facing_refusal(question,reason),"citations":[],"evidence":[],"refusal_reason":reason}
        context = "\n\n".join(f"[PMID {d.metadata['pmid']}] {d.metadata['title']}\n{d.page_content}" for d,_ in evidence)
        prompt = ("You are a biomedical literature assistant. Answer only from the supplied PubMed abstracts. "
                  "First check whether the abstracts directly contain the requested fact. When they do, answer the question directly in 1-3 concise sentences; do not abstain merely because evidence is limited or cohort-specific. "
                  "Do not use prior knowledge to fill gaps, infer individual risk, diagnose, or present association as causation. "
                  "If evidence does not directly support the answer, or the question asks for a clinical recommendation, screening schedule, "
                  "individualized risk estimate, or lifestyle effect that these abstracts do not explicitly establish, return exactly ABSTAIN. "
                  "Cite supporting sources inline as [PMID: number]. "
                  "Use no PMID that is absent from the evidence. Do not include [ABSTAIN] after answering.\n\nQUESTION:\n"+question+"\n\nEVIDENCE:\n"+context)
        raw = self.llm.invoke(prompt).content.strip()
        allowed = {str(d.metadata["pmid"]) for d,_ in evidence}
        import re
        cited = list(dict.fromkeys(re.findall(r"\[?PMID\s*:?\s*(\d+)\]?", raw, flags=re.I)))
        bad = [p for p in cited if p not in allowed]
        if response_is_abstention(raw) or bad:
            status, citations, reason = "abstained", [], "The model abstained or returned a citation not present in retrieved evidence."
            answer = user_facing_refusal(question,reason)
        else:
            answer, status, citations, reason = raw, "answered", [p for p in cited if p in allowed], None
            if not citations:
                status, reason = "abstained", "The generated response did not contain a verifiable PMID citation."
                answer = user_facing_refusal(question,reason)
        return {"status":status,"answer":answer,"citations":citations,"evidence":[{"pmid":d.metadata["pmid"],"title":d.metadata["title"],"year":d.metadata["publication_year"],"source_url":d.metadata["source_url"],"score":round(float(s),4)} for d,s in evidence],"refusal_reason":reason}

if __name__ == "__main__":
    import sys
    if "--build" in sys.argv:
        print(f"Indexed {build_index()} abstracts")
