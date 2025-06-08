from sentence_transformers import SentenceTransformer
from qdrant_client import QdrantClient
from qdrant_client.models import Filter, SearchRequest, FieldCondition, MatchValue

# 建立連線
client = QdrantClient(host="localhost", port=6333)
model = SentenceTransformer("BAAI/bge-small-en")

# 要查的概念
query_text = "knight"
query_vector = model.encode(query_text).tolist()

# 查詢最近的 3 筆
results = client.search(
    collection_name="npc_personality",
    query_vector=query_vector,
    limit=3
)


print(f"query concept: {query_text}\n")
for hit in results:
    print(f"NPC: {hit.payload['npc']}")
    print(f"Personality: {hit.payload['content']}")
    print(f"Similarity: {hit.score:.4f}")
    print("-" * 40)

