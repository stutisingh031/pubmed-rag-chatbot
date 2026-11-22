"""Verified NCBI E-utilities ingestion. The manifest is only a list of candidate IDs."""
import json
import logging
import time
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path
import requests
from .config import CORPUS_PATH, DATA_DIR, ROOT

logger = logging.getLogger(__name__)
EUTILS = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"

def load_manifest(path: Path | None = None) -> list[str]:
    values = json.loads((path or DATA_DIR / "pmids.json").read_text(encoding="utf-8"))
    if len(values) != len(set(values)) or not all(str(v).isdigit() for v in values):
        raise ValueError("PMID manifest must contain unique numeric identifiers")
    return [str(v) for v in values]

def _text(node, path):
    found = node.find(path)
    return "".join(found.itertext()).strip() if found is not None else ""

def parse_pubmed_xml(xml: str) -> list[dict]:
    root = ET.fromstring(xml)
    records = []
    for article in root.findall(".//PubmedArticle"):
        pmid = _text(article, ".//MedlineCitation/PMID")
        title = _text(article, ".//ArticleTitle")
        abstract_parts = []
        for part in article.findall(".//Abstract/AbstractText"):
            text = "".join(part.itertext()).strip()
            label = part.attrib.get("Label") or part.attrib.get("NlmCategory")
            if text:
                abstract_parts.append(f"{label}: {text}" if label else text)
        abstract = "\n".join(abstract_parts)
        journal = _text(article, ".//Journal/Title")
        year = _text(article, ".//JournalIssue/PubDate/Year") or _text(article, ".//JournalIssue/PubDate/MedlineDate")[:4]
        authors = []
        for author in article.findall(".//AuthorList/Author"):
            name = " ".join(filter(None, [_text(author, "ForeName"), _text(author, "LastName")]))
            if name:
                authors.append(name)
        if pmid and title and abstract:
            records.append({"pmid": pmid, "title": title, "authors": authors, "journal": journal,
                            "publication_year": year, "abstract": abstract, "source": "PubMed",
                            "source_url": f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/"})
    return records

def fetch_records(pmids: list[str] | None = None, output: Path = CORPUS_PATH) -> list[dict]:
    requested = pmids or load_manifest()
    response = requests.get(f"{EUTILS}/efetch.fcgi", params={"db":"pubmed", "id":",".join(requested), "retmode":"xml"}, timeout=60,
                            headers={"User-Agent":"GeneTraitResearchAssistant/1.0 (local research prototype)"})
    response.raise_for_status()
    records = parse_pubmed_xml(response.text)
    by_id = {r["pmid"]: r for r in records}
    valid = [by_id[p] for p in requested if p in by_id]
    if len(valid) < len(requested):
        logger.warning("PubMed returned %d/%d records with non-empty abstracts; excluded %s", len(valid), len(requested), sorted(set(requested)-set(by_id)))
    if not valid:
        raise RuntimeError("No PMID candidate returned a complete PubMed abstract")
    output.parent.mkdir(parents=True, exist_ok=True)
    existing = None
    if output.exists():
        try:
            existing = json.loads(output.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            existing = None
    # Stable record comparison makes repeated ingestion a true no-op when PubMed content is unchanged.
    if existing and existing.get("records") == valid:
        logger.info("PubMed corpus unchanged (%d records); kept existing snapshot", len(valid))
        return valid
    output.write_text(json.dumps({"fetched_at_utc":datetime.now(timezone.utc).isoformat(), "source":"NCBI PubMed E-utilities", "records":valid}, ensure_ascii=False, indent=2), encoding="utf-8")
    logger.info("Saved %d verified PubMed abstracts to %s", len(valid), output)
    return valid

if __name__ == "__main__":
    from .logging_config import configure_logging
    configure_logging()
    records = fetch_records()
    print(f"Fetched {len(records)} verified abstracts; distinct PMIDs={len({r['pmid'] for r in records})}")
