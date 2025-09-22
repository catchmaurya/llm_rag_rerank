# reranker.py — temporary no-op to avoid blocking
from typing import List, Tuple

def available() -> bool:
    return False

def rerank(query: str, passages: List[Tuple[str, dict]], top_n: int = 10) -> List[Tuple[str, dict]]:
    # Just return the first top_n passages without heavy models
    return passages[:top_n]

