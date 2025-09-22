# app.py  — Lean RAG with optional rerank (tuples), FastEmbed + Qdrant + Ollama
import os
import requests
from typing import List, Tuple

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from qdrant_client import QdrantClient
from qdrant_client.http.models import ScoredPoint

# Embeddings (torch-free)
from fastembed import TextEmbedding

# Optional reranker (no-op if unavailable)
from reranker import rerank, available as reranker_available


# -------- Settings --------
QDRANT_HOST = os.getenv("QDRANT_HOST", "localhost")
QDRANT_PORT = int(os.getenv("QDRANT_PORT", "6333"))
QDRANT_COLLECTION = os.getenv("QDRANT_COLLECTION", "docs")

EMBED_MODEL = os.getenv("EMBED_MODEL", "BAAI/bge-small-en-v1.5")  # Fast & solid
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "qwen2:7b-instruct")

TOP_K = int(os.getenv("TOP_K", "16"))           # initial ANN candidates
RERANK_TOP_N = int(os.getenv("RERANK_TOP_N", "5"))
MAX_CTX_CHARS = int(os.getenv("MAX_CTX_CHARS", "500"))  # per passage in prompt


# -------- Init --------
app = FastAPI(title="Mini Domain Chat (Lean RAG)")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], allow_credentials=True,
    allow_methods=["*"], allow_headers=["*"],
)

QDR = QdrantClient(host=QDRANT_HOST, port=QDRANT_PORT)
EMB = TextEmbedding(model_name=EMBED_MODEL, cache_dir=".fastembed")


def embed_one(text: str) -> List[float]:
    # FastEmbed returns a generator → list
    return list(EMB.embed([text]))[0]


class Query(BaseModel):
    q: str
    k: int = TOP_K


SYSTEM = """You are a precise domain assistant.
Output ONLY ONE JSON object with this exact schema:
{"answer": string, "commands": [{"tool": string, "args": object}], "citations": [{"doc_id": string, "page": int}]}
Never output null. If unsure, provide a brief clarification question in "answer" and leave "commands" empty.
"""


PROMPT_FMT = """{system}

Question: {q}

Context passages (ID#page :: text):
{ctx}

Return ONLY valid JSON like:
{{"answer":"...", "commands":[{{"tool":"open_url","args":{{"url":"..."}}}}], "citations":[{{"doc_id":"...","page":0}}]}}
"""


@app.get("/health")
def health():
    ok_qdrant = True
    try:
        _ = QDR.get_collections()
    except Exception:
        ok_qdrant = False
    return {
        "ok": True,
        "qdrant": ok_qdrant,
        "reranker": reranker_available(),
        "ollama_model": OLLAMA_MODEL,
        "embed_model": EMBED_MODEL,
    }

def ask_ollama(prompt: str) -> str:
    try:
        r = requests.post(
            "http://localhost:11434/api/generate",
            json={
                "model": OLLAMA_MODEL,
                "prompt": prompt,
                "stream": False,
                "options": {
                    "format": "json",      # <— force JSON mode
                    "temperature": 0,
                    "top_p": 0.1,
                    "repeat_penalty": 1.05,
                    "num_predict": 128,     # keep tight so it won’t run long
                    "num_ctx": 4096
                }
            },
            timeout=120,
        )
        r.raise_for_status()
        return r.json().get("response", "")
    except Exception as e:
        return '{"answer":"LLM call failed: ' + str(e).replace('"','') + '","commands":[],"citations":[]}'

def build_context(query: str, k: int) -> Tuple[str, List[dict]]:
    """
    Retrieve, optionally rerank, and build prompt context string.

    Returns:
        ctx_str: lines like "[doc_id#page] text"
        payloads: list of payload dicts (aligned with ctx lines)
    """
    vec = embed_one(query)
    hits: List[ScoredPoint] = QDR.search(
        collection_name=QDRANT_COLLECTION, query_vector=vec, limit=k
    )

    # Build passages as list of (text, payload) tuples
    passages: List[Tuple[str, dict]] = []
    for h in hits:
        payload = h.payload or {}
        text = (payload.get("text") or "").replace("\n", " ")
        text = text[:MAX_CTX_CHARS]
        passages.append((text, payload))

    # Optional rerank
    passages = rerank(query, passages, top_n=RERANK_TOP_N)

    # Build context string and payload list
    lines, payloads = [], []
    for (text, payload) in passages:
        doc_id = payload.get("doc_id", "?")
        page = int(payload.get("page", 0))
        lines.append(f"[{doc_id}#{page}] {text}")
        payloads.append(payload)

    return "\n".join(lines), payloads


@app.post("/ask")
def ask(query: Query):
    ctx_str, payloads = build_context(query.q, query.k)

    if not ctx_str.strip():
        return {
            "answer": "No indexed content matched (or empty index). Run ingestion and try again.",
            "commands": [{"tool":"ingest_status","args":{}}],
            "citations": []
        }

    prompt = PROMPT_FMT.format(system=SYSTEM, q=query.q, ctx=ctx_str)
    raw = ask_ollama(prompt)

    # robust JSON clamp ...
    # robust JSON clamp + shape check
    try:
        import ujson as json
    except Exception:
        import json

    try:
        s, e = raw.find("{"), raw.rfind("}")
        candidate = raw[s:e+1] if (s != -1 and e != -1 and e > s) else raw
        data = json.loads(candidate)

        # MUST be a dict with required keys; else fallback
        required = {"answer", "commands", "citations"}
        if not isinstance(data, dict) or not required.issubset(set(data.keys())):
            raise ValueError("model returned non-conforming JSON")
        return data
    except Exception:
        return {
            "answer": (raw or "").strip()[:800] or "Model returned no content.",
            "commands": [],
            "citations": []
        }

