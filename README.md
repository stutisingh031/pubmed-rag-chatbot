🧬 Medical RAG Chatbot – Evidence-Grounded Biomedical Research Assistant
A Retrieval-Augmented Generation (RAG) chatbot that answers questions about BRCA1 and breast cancer susceptibility using a curated collection of PubMed abstracts.

The chatbot retrieves relevant research, generates responses using a locally running language model, and provides PMID citations so users can trace answers back to the source literature.
⚠️ Disclaimer: This project is an educational research prototype. It is not intended for diagnosis, treatment recommendations, or personal medical advice.

🚀 Project Overview
Finding relevant evidence across biomedical research papers can take time. This project explores how RAG can make a focused collection of scientific literature easier to search and understand.

Instead of relying only on the language model's existing knowledge, the system retrieves relevant PubMed abstracts and uses them as context when generating an answer. If the available evidence is insufficient, the chatbot is designed to decline to answer.
🎯 Key Objectives
- Build a RAG-based chatbot for a focused biomedical topic.
- Retrieve relevant evidence from PubMed abstracts.
- Generate answers grounded in retrieved literature.
- Provide PMID references for source traceability.
- Abstain when the retrieved evidence does not support an answer.
✨ Key Features
1. 🔎 PubMed Literature Retrieval
- Retrieves a selected collection of PubMed records using NCBI E-utilities.
- Parses abstracts and retains PMID, title, and publication year.
- Provides links to the original PubMed records.
2. 🧠 Retrieval-Augmented Generation
- Converts abstracts into embeddings using a Sentence Transformers model.
- Stores and searches document vectors locally with FAISS.
- Passes relevant abstracts to the language model as answer context.
3. 📚 Evidence-Based Responses
- Includes PMID citations with generated answers.
- Checks that cited PMIDs belong to the retrieved evidence.
- Refuses questions when evidence is insufficient or outside the supported scope.
4. 🖥️ Local Model and Index
- Runs the language model locally through Ollama.
- Uses a persistent local FAISS index.
- Does not require a paid LLM API key.
5. 🧪 Evaluation and Testing
- Includes a small evaluation set with answerable and unanswerable questions.
- Provides automated tests for core backend functionality.
- Reports retrieval, citation-membership, and refusal results.
🧠 Technology Stack
Category	Technology
Programming Language	Python 3.11+
Backend API	FastAPI
Frontend	React, Vite
RAG Framework	LangChain
Embedding Model	Hugging Face sentence-transformers/all-MiniLM-L6-v2
Vector Search	FAISS
Language Model	Ollama qwen2.5:3b
Literature Source	PubMed / NCBI E-utilities
Testing	Pytest


🏗️ System Architecture
The application separates literature ingestion, retrieval, generation, and the user interface.
             USER QUESTION
                   |
                   v
             REACT FRONTEND
                   |
                   v
              FASTAPI API
                   |
                   v
          QUESTION EMBEDDING
                   |
                   v
          FAISS SIMILARITY SEARCH
                   |
                   v
         RELEVANT PUBMED ABSTRACTS
                   |
                   v
          OLLAMA (QWEN 2.5:3B)
                   |
                   v
        ANSWER + PMID REFERENCES
                   |
                   v
          EVIDENCE / CITATION CHECK
                   |
                   v
             CHAT RESPONSE
🔄 RAG Workflow
1. Fetch and parse the selected PubMed abstracts.
2. Generate embeddings and build the local FAISS index.
3. Retrieve the most relevant abstracts for a user question.
4. Provide the retrieved evidence to the language model.
5. Return an answer with PMID references, or abstain if evidence is insufficient.
⚙️ Run Locally
Prerequisites
- Python 3.11+
- Node.js 20+
- Ollama installed
1. Set up the Python environment
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r backend\requirements.txt
2. Fetch abstracts and build the index
python -m backend.pubmed
python -m backend.rag --build
3. Download the language model
ollama pull qwen2.5:3b
If Ollama is not already running, start it in a separate terminal:
ollama serve
4. Start the backend
From the project root, in a separate terminal:
python -m uvicorn backend.main:app --host 127.0.0.1 --port 8000
5. Start the frontend
In another terminal:
cd frontend
Copy-Item .env.example .env
npm install
npm run dev
Open the local URL shown by Vite (usually http://localhost:5173).
📊 Evaluation
The current custom evaluation set contains 5 answerable and 2 unanswerable questions.
Metric	Result
Answerable questions answered	2/5 (40%)
Unanswerable questions correctly refused	2/2 (100%)
Expected PMID retrieval	5/5 (100%)
Citation membership checks passed	7/7 (100%)


These results reflect a small project-specific test set and should not be interpreted as general medical accuracy. PMID validation confirms that a cited PMID was retrieved; it does not prove that every claim is fully supported by the cited abstract. RAGAS was attempted, but no score was produced in the recorded run.

Run tests and evaluation from the project root:
python -m pytest -q
python -m backend.evaluate
⚠️ Limitations
- The corpus contains a small selected set of abstracts, not all PubMed literature.
- Abstracts may omit details available in full-text papers.
- The local 3B model may miss supported answers or generate errors.
- Citation membership checks do not establish claim-level entailment.
- The chatbot is not a clinical decision-support system.
🙌 Acknowledgements
- PubMed / NCBI
- Hugging Face
- FAISS
- LangChain
- Ollama
- Qwen 2.5
