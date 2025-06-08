from mem0 import MemoryClient
import datetime
import os
import time # Added for file modification time

client = MemoryClient(api_key="m0-mVuNF4wBm8DLyaxkriN43xLKia4niwRv5y01699U")

# 清除 mem0 > 72hr 的記憶
def clear_old_mem0_memories(user_id: str):
    """
    Clears memories older than 72 hours for the specified user_id from mem0.
    """
    try:
        #print(f"[mem0]: Checking for memories older than 72 hours for user_id='{user_id}'...")
        memories = client.memory(user_id=user_id)

        if not memories:
            print(f"[mem0]: No memories found for user_id='{user_id}'.")
            return

        now_utc = datetime.datetime.now(datetime.timezone.utc)
        # 代表的是：72小時前的那個時間點
        seventy_two_hours_ago = now_utc - datetime.timedelta(hours=72)
        deleted_count = 0
        processed_count = 0

        for memory_item in memories:
            processed_count += 1
            memory_id = memory_item.get("id")
            timestamp_key = "timestamp" 
            memory_timestamp_str = memory_item.get(timestamp_key)

            if not memory_id or not memory_timestamp_str:
                print(f"[mem0]: Memory item for user_id='{user_id}' is missing 'id' or '{timestamp_key}'. Item: {memory_item}")
                continue

            try:
                if memory_timestamp_str.endswith('Z'):
                    memory_timestamp_dt = datetime.datetime.fromisoformat(memory_timestamp_str.replace('Z', '+00:00'))
                else:
                    memory_timestamp_dt = datetime.datetime.fromisoformat(memory_timestamp_str)
                
                if memory_timestamp_dt.tzinfo is None:
                    memory_timestamp_dt = memory_timestamp_dt.replace(tzinfo=datetime.timezone.utc)

                if memory_timestamp_dt < seventy_two_hours_ago:
                    client.delete(memory_id)
                    print(f"[mem0]: Deleted old memory ID='{memory_id}' for user_id='{user_id}' (Timestamp: {memory_timestamp_str})")
                    deleted_count += 1
            except ValueError as ve:
                print(f"[mem0]: Could not parse timestamp '{memory_timestamp_str}' for memory ID='{memory_id}'. Error: {ve}")
            except Exception as e:
                print(f"[mem0]: Error processing memory ID='{memory_id}' for user_id='{user_id}': {e}")
        
        # This print statement was missing from the original snippet, adding it back for completeness
        print(f"[mem0]: Processed {processed_count} memories for user_id='{user_id}'. Deleted {deleted_count} memories older than 72 hours.")

    except Exception as e:
        print(f"[mem0]: Failed to clear old memories for user_id='{user_id}': {e}")

# 清除本地端 > 72hr 的記憶
def clear_old_local_session_files(directory="monitor_memory", hours_threshold=72):
    now_ts = time.time()
    threshold_seconds = hours_threshold * 3600
    deleted_count = 0
    processed_count = 0

    if not os.path.exists(directory):
        print(f"[LocalCleanup]: Directory '{directory}' does not exist. Nothing to clean.")
        return

    try:
        for filename in os.listdir(directory):
            if filename.endswith(".json"):
                processed_count += 1
                filepath = os.path.join(directory, filename)
                try:
                    file_mod_time = os.path.getmtime(filepath)
                    if (now_ts - file_mod_time) > threshold_seconds:
                        os.remove(filepath)
                        print(f"[LocalCleanup]: Deleted old local file: {filepath} (Last modified: {datetime.datetime.fromtimestamp(file_mod_time).isoformat()})")
                        deleted_count += 1
                except Exception as e:
                    print(f"[LocalCleanup]: Error processing file {filepath}: {e}")
    except Exception as e:
        print(f"[LocalCleanup]: Error listing files in directory '{directory}': {e}")


if __name__ == "__main__":

    # 1. Clear old mem0 cloud memories
    print("[MainScript]: --- Clearing mem0 Cloud Memories ---")
    try:
        all_user_ids = client.list_user_ids() 
        if not all_user_ids:
            print("[MainScript]: No user_ids found in mem0 to process.")
        else:
            for user_id in all_user_ids:
                clear_old_mem0_memories(user_id)
    except Exception as e:
        print(f"[MainScript]: Error during the mem0 cleanup process: {e}")

    # 2. Clear old local session files
    print("[MainScript]: --- Clearing Local Session Files ---")
    try:
        clear_old_local_session_files(directory="monitor_memory", hours_threshold=72)
    except Exception as e:
        print(f"[MainScript]: Error during local file cleanup: {e}")
    
    print("[MainScript]: --- Cleanup process completed. ---")
