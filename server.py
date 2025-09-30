from flask import Flask, request, jsonify
import json, uuid, os, datetime, re, time
from sentence_transformers import SentenceTransformer
from monitorMem import insert_monitor_to_mem0
from mem0 import MemoryClient
from collections import Counter

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

def insert_monitor_chunk_to_mem0(mem0_data):
    try:
        mem_client.add(
            messages=[{"role":"assistant", "content": mem0_data["content"]}],
            user_id=mem0_data["user_id"],
            metadata=mem0_data.get("metadata", {})
        )
    except Exception as e:
        print(f"[mem0] Upload failed: {e}", flush=True)

# 找主角

NON_NAMES = {"The","A","An","He","She","They","It","I","We","You"}
TITLE_WORDS = {"Sir","Lady","Lord","King","Queen","Prince","Princess","Master","Doctor"}

def find_protagonist(text: str) -> str | None:
    if not text:
        return None

    # 大寫
    tokens = re.findall(r"\b[A-Z][a-z]+(?:'[A-Za-z]+)?\b", text)
    if not tokens:
        return None

    # 非name
    filtered = []
    for i, tok in enumerate(tokens):
        if tok in NON_NAMES:
            continue
        prev = tokens[i-1] if i > 0 else ""
        if prev in TITLE_WORDS:
            continue
        filtered.append(tok)

    if not filtered:
        return None

    counts = Counter(filtered)
    most_common_name, freq = counts.most_common(1)[0]

    first_name = None
    for tok in tokens:
        if tok in filtered:
            first_name = tok
            break

    if first_name == most_common_name:
        print(f"[Protagonist]: {first_name} (freq: {freq})", flush=True)
        return first_name
    else:
        print(f"[Protagonist]: {most_common_name} (freq: {freq})", flush=True)
        return most_common_name
    return None

def get_protagonist(user_id: str, title: str | None = None) -> str | None:
    return get_canon_value(user_id, "protagonist", title)

def write_protagonist_canon(user_id: str, title: str, name: str) -> None:
    if not name:
        return
    try:
        mem_client.add(
            messages=[{"role": "assistant", "content": f"[CANON] protagonist: {name}"}],
            user_id=user_id,
            metadata={
                "kind": "canon",
                "key": "protagonist",
                "value": name,
                "title": title or "unknown",
                "timestamp": int(time.time()),
            },
        )
    except Exception as e:
        print(f"[Server] write_protagonist_canon failed: {e}", flush=True)

@app.post("/get_protagonist")
def get_protagonist_api():
    data = request.get_json(force=True) or {}
    session = data.get("session") or {}
    mon = (session.get("monitor") if isinstance(session, dict) else {}) or {}
    user_id = mon.get("session_id") or data.get("user_id") or ""
    if not user_id:
        return jsonify({"protagonist": None}), 200

    name = get_protagonist(user_id)
    if not name:
        filename = os.path.join("monitor_memory", f"{user_id}.json")
        if os.path.exists(filename):
            try:
                with open(filename, "r", encoding="utf-8") as f:
                    data = json.load(f)
                stories = data.get("monitor_stories", [])
                if stories:
                    full_text = "\n\n".join(s.get("chunk_text", "") for s in stories)
                    name = find_protagonist(full_text)
            except:
                pass
    return jsonify({"protagonist": name}), 200

def get_canon_value(user_id: str, key: str, title: str | None = None) -> str | None:
    q = f"[CANON] {key}"
    try:
        res = mem_client.search(
            q,
            version="v2",
            filters={"AND": [{"user_id": user_id}]},  
            limit=5, threshold=0.0, graph=False, rerank=False
        ) or []
        import re
        pattern = rf"\[CANON\]\s*{re.escape(key)}\s*[:=]\s*(.+)"
        for r in res:
            text = (r.get("memory") or "").strip()
            m = re.search(pattern, text)
            if m:
                return m.group(1).strip()
    except Exception as e:
        print(f"[Server] get_canon_value failed: {e}", flush=True)
    return None


@app.route("/upload_monitor", methods=["POST"])
def insert_monitor_story():
    data = request.json or {}

    mon = (data.get("monitor") or {})
    session_id = mon.get("session_id") or data.get("user_id")
    incoming_piece = (mon.get("text") or mon.get("intro") or data.get("text") or "").strip()
    title = mon.get("title") or data.get("title") or "unknown"
    timestamp = mon.get("timestamp") or data.get("timestamp")

    if not session_id:
        print("[Server] Error: session_id or user_id is missing", flush=True)
        return jsonify({"error": "session_id or user_id is required"}), 400
    if not incoming_piece:
        print("[Server] Error: No text content provided", flush=True)
        return jsonify({"error": "No text content provided"}), 400

    monitor_stories, all_npc_choices = [], []
    os.makedirs("monitor_memory", exist_ok=True)
    filename = os.path.join("monitor_memory", f"{session_id}.json")
    
    if os.path.exists(filename):
        try:
            with open(filename, "r", encoding="utf-8") as f:
                prev = json.load(f)
            monitor_stories = prev.get("monitor_stories", [])
            all_npc_choices = prev.get("npc_choices", [])
        except Exception as e:
            print(f"[Server] Warn: load file failed: {e}", flush=True)

    if monitor_stories:
        last_chunk = (monitor_stories[-1].get("chunk_text") or "").strip()
        if incoming_piece == last_chunk:
            return jsonify({
                "status": "skipped_duplicate",
                "session_id": session_id,
                "sequence": len(monitor_stories) - 1
            }), 200

    prev_full = monitor_stories[-1]["full_intro"] if monitor_stories else ""
    temp_full = (prev_full + ("\n\n" if prev_full else "") + incoming_piece)

    sequence = len(monitor_stories)
    new_story = {
        "timestamp": timestamp,
        "title": title,
        "full_intro": temp_full,        
        "chunk_text": incoming_piece,   
        "sequence": sequence
    }
    monitor_stories.append(new_story)


    MAX_KEEP = 10
    if len(monitor_stories) > MAX_KEEP:
        monitor_stories = monitor_stories[-MAX_KEEP:]

    for i, s in enumerate(monitor_stories):
        s["sequence"] = i

    kept_full = "\n\n".join(s.get("chunk_text", "") for s in monitor_stories).strip()
    monitor_stories[-1]["full_intro"] = kept_full

    try:
        with open(filename, "w", encoding="utf-8") as f:
            json.dump({
                "monitor_stories": monitor_stories,
                "npc_choices": all_npc_choices,
                "session_id": session_id
            }, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"[Server] Error: write file failed: {e}", flush=True)
        return jsonify({"error": "write failed"}), 500

    # 同步到 mem0：只上傳最新片段
    try:
        insert_monitor_chunk_to_mem0({
            "user_id": session_id,
            "content": incoming_piece,
            "metadata": {
                "kind": "paragraph",
                "title": monitor_stories[-1]["title"],
                "sequence": monitor_stories[-1]["sequence"],
                "timestamp": monitor_stories[-1]["timestamp"]
            }
        })
    except Exception as e:
        print(f"[Server] Warn: mem0 sync failed: {e}", flush=True)

    
    try:
        existing = get_canon_value(session_id, "protagonist", title)
        if not existing:
            cand = find_protagonist(kept_full) 
            if cand:
                write_protagonist_canon(session_id, title, cand)
    except Exception as e:
        print(f"[Server] protagonist detect failed: {e}", flush=True)

    return jsonify({
        "status": "ok",
        "session_id": session_id,
        "sequence": monitor_stories[-1]["sequence"]
    }), 200

# 去mem0 找資料
@app.route("/query_monitor", methods=["POST"])
def query_monitor_memory():
    data = request.json or {}
    query     = data.get("query", "")
    user_id   = data.get("user_id", "")
    top_k     = int(data.get("top_k", 6))
    min_score = float(data.get("min_score", 0.25))

    print(f"[query_monitor] user={user_id} min={min_score} top={top_k} q='{query[:120]}'", flush=True)

    def do_search(thr):
        res = mem_client.search(
            query, version="v2",
            filters={"OR":[{"user_id": user_id}]},
            limit=max(top_k, 8),  
            threshold=thr, graph=False, rerank=False
        ) or []
        return res

    results = do_search(min_score)
    for i, r in enumerate(results):
        print(f"[mem0] hit {i} score={r.get('score')} meta={r.get('metadata')}", flush=True)

    if not results:
        import time
        for thr in [max(0.0, min_score - 0.10), max(0.0, min_score - 0.20)]:
            time.sleep(0.35)
            results = do_search(thr)
            if results:
                break
    def _extract_content(r):
        # 直接抓 memory 欄位
        content = r.get("memory", "")
        if content:
            return content.strip()
        # 其他 fallback
        md = r.get("metadata") or {}
        if md.get("kind") == "canon" and md.get("value"):
            return str(md.get("value")).strip()
        return ""

    # 過濾和清理結果
    clean_results = []
    for r in results:
        content = _extract_content(r)
        if not content:
            continue
        clean_results.append({
            "memory": content,
            "score": float(r.get("score") or 0.0)
        })

    prot = get_protagonist(user_id)
    if prot:
        clean_results.sort(
            key=lambda r: (
                prot in r["memory"],
                float(r["score"])
            ),
            reverse=True   
        )

    print(f"[query_monitor] found {len(clean_results)} valid results", flush=True)
    for i, r in enumerate(clean_results[:5]):  # 只印前5個
        print(f"[query_monitor] {i+1}) score={r['score']:.2f} content='{r['memory'][:100]}{'...' if len(r['memory']) > 100 else ''}'", flush=True)

    return jsonify(clean_results)

# NPC FreeTalk 記憶
@app.route("/upload_npc", methods=["POST"])
def upload_npc_memory():
    data = request.json or {}

    if "content" in data and "user_id" in data:
        user_id = data["user_id"]
        content = data["content"] or ""
        meta = data.get("metadata", {}) or {}

        os.makedirs("monitor_memory", exist_ok=True)
        filename = f"monitor_memory/{user_id}.json"
        monitor_stories, all_npc_choices = [], []
        if os.path.exists(filename):
            try:
                with open(filename, "r", encoding="utf-8") as f:
                    prev = json.load(f)
                    monitor_stories = prev.get("monitor_stories", [])
                    all_npc_choices = prev.get("npc_choices", [])
            except Exception:
                pass

        sequence = int(meta.get("sequence", len(monitor_stories)))

        monitor_stories.append({
            "timestamp": meta.get("timestamp"),
            "title":     meta.get("title"),
            "full_intro": (monitor_stories[-1]["full_intro"] + "\n\n" + content) if monitor_stories else content,
            "chunk_text": content,
            "sequence":   sequence
        })

        with open(filename, "w", encoding="utf-8") as f:
            json.dump({"monitor_stories": monitor_stories,
                       "npc_choices": all_npc_choices,
                       "session_id": user_id}, f, ensure_ascii=False, indent=2)

        insert_monitor_chunk_to_mem0({
            "user_id": user_id,
            "content": content,
            "metadata": {
                "title": meta.get("title"),
                "sequence": sequence,
                "answer_key": meta.get("answer_key"),
                "timestamp": meta.get("timestamp")
            }
        })
        return {"status": "ok", "session_id": user_id, "sequence": sequence}

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

@app.route("/clear_all_memory", methods=["POST"])
def clear_all_memory():
    import shutil
    try:
        shutil.rmtree("monitor_memory", ignore_errors=True)
        os.makedirs("monitor_memory", exist_ok=True)
        return jsonify({"status": "ok", "message": "All memory cleared."}), 200
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000)


