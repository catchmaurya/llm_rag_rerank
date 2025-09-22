# settings.py
QDRANT_HOST = "localhost"
QDRANT_PORT = 6333
QDRANT_COLLECTION = "docs"

# Embedding model (fast & solid)
EMBED_MODEL = "BAAI/bge-small-en-v1.5"  # ~384-dim, good speed/quality

# LLM via Ollama
OLLAMA_MODEL = "mistral:instruct"       # or "qwen2:7b-instruct"

# Chunking
CHUNK_SIZE = 800
CHUNK_OVERLAP = 120

# Retrieval
TOP_K = 32              # ANN candidates
RERANK_TOP_N = 10       # after cross-encoder rerank, pass top N to prompt
MAX_CTX_CHARS = 1200    # per passage in prompt (trim to keep prompt small)

