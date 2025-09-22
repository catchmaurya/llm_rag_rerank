
## Start

# Lightweight Domain-Specific LLM with Ollama, FastAPI & Qdrant

This repo shows how to build a **local, domain-specific LLM assistant** that runs entirely on your machine.  
It uses open-source components only:

- [Ollama](https://ollama.com) → run open-source LLMs locally (`mistral:instruct`, `qwen2:7b-instruct`, etc.)  
- [FastAPI](https://fastapi.tiangolo.com) → simple API server  
- [Qdrant](https://qdrant.tech) → vector database for storing & searching embeddings  
- [FastEmbed](https://github.com/qdrant/fastembed) → lightweight, efficient embeddings  

---

## 🚀 Quickstart

###  Install Ollama
```bash
brew install ollama
ollama serve
ollama pull mistral:instruct


###  Run Qdrant (Vector DB)
docker run -p 6333:6333 -v qdrant_storage:/qdrant qdrant/qdrant


### Python Environment
python3 -m venv .venv
source .venv/bin/activate
pip install fastapi uvicorn[standard] qdrant-client fastembed requests ujson

### load text files in corpus folder
python extracter.py dummy.pdf --out corpus/


### Runserver
python ingest.py
uvicorn app:app --reload

### Test
curl -X POST http://127.0.0.1:8000/ask \
  -H "Content-Type: application/json" \
  -d '{"q":"What is in my documents?"}'
-- {"answer": "summary of your docs ..."}

### debug commands

ollama list                   # ensure your model is present

--------

# 1) Is the API alive?
curl -s http://127.0.0.1:8000/health

# 2) Do you have points in Qdrant?
curl -s http://127.0.0.1:6333/collections | jq .
curl -s http://127.0.0.1:6333/collections/docs | jq .

# 3) Does Ollama reply instantly?
curl -s http://localhost:11434/api/tags | jq .
curl -s http://localhost:11434/api/generate \
  -d '{"model":"mistral:instruct","prompt":"Return ONLY this JSON: {\"ok\":true}","stream":false}' | jq .

curl --max-time 15 -v -X POST "http://127.0.0.1:8000/ask" \
  -H "Content-Type: application/json" \
  -d '{"q":"Say hi"}'

curl --max-time 15 -v -X POST "http://127.0.0.1:8000/ask" \
  -H "Content-Type: application/json" \
  -d '{"q":"Say hi"}'
