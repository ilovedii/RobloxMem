import json
import datetime
from sentence_transformers import SentenceTransformer
from qdrant_client import QdrantClient
from qdrant_client.models import PointStruct, VectorParams, Distance

def log_time(msg):
    print(f"[{datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]}] {msg}")

# Qdrant（本地）
client = QdrantClient(host="localhost", port=6333)

# 建立 collection cosine similarity
client.recreate_collection(
    collection_name="npc_personality",
    vectors_config=VectorParams(size=384, distance=Distance.COSINE)
)
print("新的 npc_personality collection 已建立")

# 向量模型：BAAI/bge-small-en
log_time("載入 文字轉向量 模型")
model = SentenceTransformer("BAAI/bge-small-en")
log_time("模型載入完成")

# 讀 npc_memory_dataset.json
with open("npc_memory_dataset.json", "r", encoding="utf-8") as f:
    data = json.load(f)

log_time("開始產生向量")
points = []
for i, entry in enumerate(data):
    vector = model.encode(entry["content"]).tolist()
    points.append(
        PointStruct(
            id=i,
            vector=vector,
            payload={
                "npc": entry["npc"],
                "tag": entry["tag"],
                "content": entry["content"]
            }
        )
    )
log_time("向量產生完成")

# 上傳到 Qdrant
log_time("開始上傳到 Qdrant（npc_personality）")
client.upsert(collection_name="npc_personality", points=points)
log_time("上傳完成")

