import json
from pathlib import Path

import pytest

from backend.pubmed import load_manifest, parse_pubmed_xml
from backend.evaluate import score_case
from backend.rag import response_is_abstention


def test_pubmed_parser_preserves_metadata_and_structured_abstract():
    xml = """<PubmedArticleSet><PubmedArticle><MedlineCitation><PMID>123456</PMID><Article><ArticleTitle>BRCA1 &amp; repair</ArticleTitle><AuthorList><Author><ForeName>A</ForeName><LastName>Researcher</LastName></Author></AuthorList><Journal><Title>Journal</Title><JournalIssue><PubDate><Year>2024</Year></PubDate></JournalIssue></Journal><Abstract><AbstractText Label='RESULTS'>Finding one.</AbstractText><AbstractText>Finding two.</AbstractText></Abstract></Article></MedlineCitation></PubmedArticle></PubmedArticleSet>"""
    record = parse_pubmed_xml(xml)[0]
    assert record["pmid"] == "123456"
    assert record["title"] == "BRCA1 & repair"
    assert record["authors"] == ["A Researcher"]
    assert record["publication_year"] == "2024"
    assert "RESULTS: Finding one." in record["abstract"]
    assert "Finding two." in record["abstract"]


def test_pubmed_parser_excludes_record_without_abstract():
    xml = "<PubmedArticleSet><PubmedArticle><MedlineCitation><PMID>123</PMID><Article><ArticleTitle>Title</ArticleTitle></Article></MedlineCitation></PubmedArticle></PubmedArticleSet>"
    assert parse_pubmed_xml(xml) == []


def test_manifest_has_twenty_unique_pmids():
    values = load_manifest()
    assert len(values) == 20
    assert len(set(values)) == 20


def test_golden_set_has_exact_required_mix_and_references_corpus():
    cases = json.loads((Path(__file__).parents[1] / "evaluation" / "golden_cases.json").read_text(encoding="utf-8"))
    records = json.loads((Path(__file__).parents[1] / "backend/data/pubmed_abstracts.json").read_text(encoding="utf-8"))["records"]
    pmids = {r["pmid"] for r in records}
    assert len(cases) == 7
    assert sum(c["answerable"] for c in cases) == 5
    assert all(set(c["expected_pmids"]) <= pmids for c in cases if c["answerable"])
    assert all(not c["expected_pmids"] for c in cases if not c["answerable"])


def test_metric_scoring_checks_retrieval_and_citations():
    case = {"id":"A","answerable":True,"expected_pmids":["1"]}
    result = {"status":"answered","citations":["9"],"evidence":[{"pmid":"1"}],"answer":"x"}
    scored = score_case(case,result)
    assert scored["expected_pmid_retrieval"] is True
    assert scored["citation_validity"] is False
    assert scored["unsupported_citation_count"] == 1


def test_refusal_text_is_not_counted_as_an_answer_even_if_it_mentions_a_pmid():
    assert response_is_abstention("The requested rate is not explicitly stated in the provided evidence. [PMID: 17018160] [ABSTAIN]")
    assert not response_is_abstention("The study reports 6 of 204 cases (2.9%) [PMID: 17018160].")


def test_api_health_corpus_and_chat_response_shape(monkeypatch):
    import backend.rag as rag_module

    class FakeRAG:
        store = object()
        llm = object()
        index_error = None
        def answer(self, question):
            return {"status":"answered","answer":"Supported. [PMID: 7545954]","citations":["7545954"],
                    "evidence":[{"pmid":"7545954","title":"BRCA1","year":"1994","source_url":"https://pubmed.ncbi.nlm.nih.gov/7545954/","score":0.8}],"refusal_reason":None}

    monkeypatch.setattr(rag_module,"ResearchRAG",FakeRAG)
    from backend import main
    monkeypatch.setattr(main,"rag",FakeRAG())
    monkeypatch.setattr(main,"ollama_health",lambda:{"available":True,"model":"qwen2.5:3b","error":None})
    assert main.health()["ready"] is True
    assert main.corpus_summary()["count"] == 20
    response = main.chat(main.ChatRequest(question="What did early BRCA1 evidence show?"))
    assert response["citations"] == ["7545954"]
    assert response["evidence"][0]["source_url"].endswith("/7545954/")
    paths = main.app.openapi()["paths"]
    assert {"/api/health","/api/corpus","/api/chat"} <= set(paths)

