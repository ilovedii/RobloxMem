from mem0 import MemoryClient
import uuid
import datetime

# mem0 的 API
client = MemoryClient(api_key="m0-mVuNF4wBm8DLyaxkriN43xLKia4niwRv5y01699U")

def insert_monitor_to_mem0(entry):
    timestamp = datetime.datetime.utcnow().isoformat()
    session_id = entry.get("monitor", {}).get("session_id", str(uuid.uuid4()))
    story_text = entry.get("monitor", {}).get("intro", "")
    npc_id = "unknown"

    if entry.get("npc_choices"):
        npc_id = entry["npc_choices"][-1].get("npc_id", "unknown")

    messages = [
            {
                "role": "user",
                "content": f"Story: {story_text}"
                },
            {
                "role": "assistant",
                "content": f"The player met NPC {npc_id} in this scene."
                }
            ]

    try:
        client.add(messages, user_id=session_id)
        print("[mem0]: 成功寫入 mem0 雲端記憶")
    except Exception as e:
        print("[mem0]: 上傳失敗:", e)

