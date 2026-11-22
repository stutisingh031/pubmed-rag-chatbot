"""Run the seven inspected-corpus cases and compute custom refusal/citation/retrieval metrics."""
import json
import logging
import sys
from pathlib import Path
from .config import ROOT
from .rag import ResearchRAG
from .logging_config import configure_logging

CASES = ROOT / "evaluation" / "golden_cases.json"
RESULTS = ROOT / "evaluation" / "results.json"
logger = logging.getLogger(__name__)

def score_case(case: dict, result: dict) -> dict:
    retrieved = {str(e["pmid"]) for e in result["evidence"]}
    cited = {str(p) for p in result["citations"]}
    expected = {str(p) for p in case["expected_pmids"]}
    answerable = case["answerable"]
    refused = result["status"] == "abstained"
    return {"id":case["id"],"answerable":answerable,"status":result["status"],
            "refusal_correct":refused == (not answerable),
            "citation_validity":(not cited) if refused else (bool(cited) and len(cited-set(retrieved)) == 0),
            "expected_pmid_retrieval":bool(expected & retrieved) if expected else None,
            "unsupported_citation_count":len(cited-set(retrieved)),"citation_present":bool(cited),"retrieved_pmids":sorted(retrieved),
            "citations":sorted(cited),"answer":result["answer"]}

def run_ragas(cases: list[dict], scored: list[dict]) -> dict:
    from datasets import Dataset
    from ragas import evaluate as ragas_evaluate
    from ragas.embeddings import LangchainEmbeddingsWrapper
    from ragas.metrics._answer_similarity import AnswerSimilarity
    from ragas.run_config import RunConfig
    from .config import EMBEDDING_MODEL
    from langchain_huggingface import HuggingFaceEmbeddings

    record_by_id = {r["pmid"]:r for r in json.loads((ROOT/"backend/data/pubmed_abstracts.json").read_text(encoding="utf-8"))["records"]}
    rows = []
    for case, result in zip(cases, scored):
        if case["answerable"]:
            docs = [record_by_id[str(pmid)] for pmid in result["retrieved_pmids"]]
            contexts = [d["abstract"] for d in docs]
            rows.append({"question":case["question"],"answer":result["answer"],"contexts":contexts,"ground_truth":case["reference_answer"],
                         "user_input":case["question"],"response":result["answer"],"retrieved_contexts":contexts,"reference":case["reference_answer"]})
    local_embeddings = LangchainEmbeddingsWrapper(HuggingFaceEmbeddings(model_name=EMBEDDING_MODEL,model_kwargs={"device":"cpu"},encode_kwargs={"normalize_embeddings":True}))
    metric = AnswerSimilarity(embeddings=local_embeddings)
    result = ragas_evaluate(Dataset.from_list(rows),metrics=[metric],embeddings=local_embeddings,
                            run_config=RunConfig(timeout=180,max_retries=0,max_workers=1),raise_exceptions=True,show_progress=False)
    return {"status":"partial","scope":"five answerable cases only","metrics":["answer_similarity"],
            "scores":result.to_pandas().to_dict(orient="records"),
            "faithfulness_status":"unavailable","faithfulness_note":"The Ollama faithfulness judge exceeded RAGAS's 240-second per-sample timeout on this CPU-only host."}

def run_ragas_only():
    configure_logging()
    saved = json.loads(RESULTS.read_text(encoding="utf-8"))
    cases = json.loads(CASES.read_text(encoding="utf-8"))
    try:
        saved["ragas"] = run_ragas(cases,saved["cases"])
        logger.info("RAGAS answer-similarity evaluation completed for five answerable cases")
    except Exception as exc:
        saved["ragas"] = {"status":"unavailable","error":str(exc) or type(exc).__name__,"scope":"five answerable cases only","metrics":["answer_similarity"]}
        logger.exception("RAGAS local judge failed")
    RESULTS.write_text(json.dumps(saved,indent=2),encoding="utf-8")
    print(json.dumps(saved["ragas"],indent=2))

def run(include_ragas: bool = False):
    configure_logging()
    rag = ResearchRAG()
    if not rag.store:
        raise RuntimeError(rag.index_error)
    cases = json.loads(CASES.read_text(encoding="utf-8"))
    if len(cases) != 7 or sum(c["answerable"] for c in cases) != 5:
        raise ValueError("Golden set must contain exactly five answerable and two unanswerable cases")
    scored = []
    for case in cases:
        result = rag.answer(case["question"])
        scored.append(score_case(case,result))
        logger.info("Evaluation case %s status=%s retrieved=%d citations=%d",case["id"],result["status"],len(result["evidence"]),len(result["citations"]))
        print(f"Completed {case['id']}: {result['status']}",flush=True)
    custom = {"answerable_success_rate":sum(r["status"]=="answered" for r in scored if r["answerable"])/5,
              "unanswerable_refusal_accuracy":sum(r["refusal_correct"] for r in scored if not r["answerable"])/2,
              "refusal_accuracy_all":sum(r["refusal_correct"] for r in scored)/7,
              "citation_validity":sum(r["citation_validity"] for r in scored)/7,
              "answered_citation_presence_rate":sum(r["citation_present"] for r in scored if r["status"]=="answered")/max(1,sum(r["status"]=="answered" for r in scored)),
              "expected_pmid_hit_rate":sum(r["expected_pmid_retrieval"] for r in scored if r["expected_pmid_retrieval"] is not None)/5,
              "false_positive_abstention_count":sum(r["answerable"] and r["status"]=="abstained" for r in scored),
              "false_negative_abstention_count":sum((not r["answerable"]) and r["status"]=="answered" for r in scored)}
    RESULTS.parent.mkdir(parents=True,exist_ok=True)
    output_ragas = {"status":"not_run","scope":"five answerable cases only","note":"Run python -m backend.evaluate --ragas to attempt local RAGAS scoring."}
    RESULTS.write_text(json.dumps({"metrics":custom,"cases":scored,"ragas":output_ragas},indent=2),encoding="utf-8")
    if include_ragas:
        try:
            output_ragas = run_ragas(cases,scored)
        except Exception as exc:
            output_ragas = {"status":"unavailable","error":str(exc) or type(exc).__name__,"scope":"five answerable cases only","note":"Custom metrics are still reported; RAGAS did not complete."}
    output = {"metrics":custom,"cases":scored,"ragas":output_ragas}
    RESULTS.write_text(json.dumps(output,indent=2),encoding="utf-8")
    logger.info("Evaluation complete; custom_metrics=%s ragas_status=%s",custom,output_ragas["status"])
    print(json.dumps(custom,indent=2))

if __name__ == "__main__":
    if "--ragas-only" in sys.argv:
        run_ragas_only()
    else:
        run(include_ragas="--ragas" in sys.argv)
