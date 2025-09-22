# ingest.py
import glob
from qdrant_client import QdrantClient
from qdrant_client.http.models import Distance, VectorParams, PointStruct
from sentence_transformers import SentenceTransformer
from settings import *
import os

EMB = SentenceTransformer(EMBED_MODEL)
QDR = QdrantClient(host=QDRANT_HOST, port=QDRANT_PORT)

def chunks(text, size=CHUNK_SIZE, overlap=CHUNK_OVERLAP):
    words = text.split()
    i = 0
    while i < len(words):
        yield " ".join(words[i:i+size])
        i += size - overlap

def ensure_collection():
    try:
        QDR.get_collection(QDRANT_COLLECTION)
    except:
        QDR.recreate_collection(
            collection_name=QDRANT_COLLECTION,
            vectors_config=VectorParams(size=EMB.get_sentence_embedding_dimension(),
                                        distance=Distance.COSINE)
        )

def ingest_folder(folder="corpus"):
    ensure_collection()
    pid = 0
    batch = []
    for fp in glob.glob(os.path.join(folder, "*")):
        if os.path.isdir(fp): 
            continue
        with open(fp, "r", encoding="utf-8", errors="ignore") as f:
            raw = f.read()
        page = 0
        for ch in chunks(raw):
            vec = EMB.encode(ch).tolist()
            batch.append(PointStruct(
                id=pid, vector=vec,
                payload={"doc_id": os.path.basename(fp), "page": page, "text": ch}
            ))
            pid += 1; page += 1
            if len(batch) >= 256:
                QDR.upsert(collection_name=QDRANT_COLLECTION, points=batch); batch=[]
    if batch:
        QDR.upsert(collection_name=QDRANT_COLLECTION, points=batch)

if __name__ == "__main__":
    ingest_folder()
    print("Ingest complete.")

