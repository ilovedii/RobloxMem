from flask import Flask, request, jsonify
import json, uuid, os, datetime
from sentence_transformers import SentenceTransformer
from monitorMem import insert_monitor_to_mem0
from mem0 import MemoryClient

app = Flask(__name__)
model = SentenceTransformer("BAAI/bge-small-en")
mem_client = MemoryClient(api_key="m0-mVuNF4wBm8DLyaxkriN43xLKia4niwRv5y01699U")
seen_sessions = set()

def log_time(msg):
    print(f"[{datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]}] {msg}")

# encode endpoint: 把文字變向量
@app.route("/encode", methods=["POST"])
def encode_text():
    try:
        data = request.json
        text = data.get("text", "")
        if not text:
            return {"error": "No text provided"}, 400
        vector = model.encode(text).tolist()
        return jsonify({"vector": vector})
    except Exception as e:
        return {"error": str(e)}, 500

# 上傳故事mem
@app.route("/upload_monitor", methods=["POST"])
def receive_monitor_story():
    data = request.json
    monitor = data.get("monitor", {})
    npc_choices = data.get("npc_choices", [])
    
    # 每次新 session 代表新故事
    session_id = monitor.get("session_id", str(uuid.uuid4()))
    data["monitor"]["session_id"] = session_id

    os.makedirs("monitor_memory", exist_ok=True)
    filename = f"monitor_memory/{session_id}.json"
    monitor_stories = []
    prev_npc_choices = []

    if os.path.exists(filename):
        try:
            with open(filename, "r", encoding="utf-8") as f:
                prev_data = json.load(f)
                monitor_stories = prev_data.get("monitor_stories", [])
                prev_npc_choices = prev_data.get("npc_choices", [])
        except Exception:
            pass

    # 新故事
    monitor_stories.append({
        "timestamp": monitor.get("timestamp"),
        "title": monitor.get("title"),
        "intro": monitor.get("intro")
    })

    # 寫入新的 JSON（monitor + npc_choices）
    with open(filename, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    # 上傳到 mem0 雲端記憶
    insert_monitor_to_mem0(data)

    return {"status": "ok"}

# 去mem0 找資料
@app.route("/query_monitor", methods=["GET"])
def query_monitor_memory():
    query = request.args.get("query", "")
    user_id = request.args.get("user_id", "")
    if not query or not user_id:
        return jsonify({"error": "缺少 query 或 user_id"}), 400

    try:
        results = mem_client.search(query, user_id=user_id)
        return jsonify(results)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# NPC FreeTalk 記憶
@app.route("/upload_npc", methods=["POST"])
def upload_npc_memory():
    try:
        data = request.json
        user_id = data.get("user_id")
        message = data.get("message")
        reply = data.get("reply")

        if not user_id or not message or not reply:
            return jsonify({"error": "缺少 user_id 或 message 或 reply"}), 400

        messages = [
            {"role": "user", "content": message},
            {"role": "assistant", "content": reply}
        ]

        mem_client.add(messages, user_id=user_id)
        print(f"[Server]: 上傳 NPC 記憶成功 for {user_id}")
        return jsonify({"status": "ok"})

    except Exception as e:
        print(f"[mem0]: 上傳 NPC 記憶失敗: {e}")
        return jsonify({"error": str(e)}), 500

@app.route("/query_npc", methods=["GET"])
def query_npc_memory():
    query = request.args.get("query", "")
    user_id = request.args.get("user_id", "")
    if not query or not user_id:
        return jsonify({"error": "缺少 query 或 user_id"}), 400

    try:
        results = mem_client.search(query, user_id=user_id)
        return jsonify(results)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000)


