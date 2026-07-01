import json
import os
from datetime import datetime

LOG_FILE = "logs/audit.jsonl"

def init_db():
    os.makedirs(os.path.dirname(LOG_FILE), exist_ok=True)

def save_submission(record: dict):
    init_db()
    with open(LOG_FILE, "a") as f:
        f.write(json.dumps(record) + "\n")

def get_record(content_id: str) -> dict | None:
    if not os.path.exists(LOG_FILE):
        return None
    with open(LOG_FILE, "r") as f:
        for line in f:
            record = json.loads(line.strip())
            if record.get("content_id") == content_id:
                return record
    return None

def update_record_status(content_id: str, creator_reasoning: str) -> bool:
    if not os.path.exists(LOG_FILE):
        return False
    
    updated = False
    records = []
    
    with open(LOG_FILE, "r") as f:
        for line in f:
            record = json.loads(line.strip())
            if record.get("content_id") == content_id:
                record["status"] = "under_review"
                record["appeal_reasoning"] = creator_reasoning
                updated = True
            records.append(record)
            
    if updated:
        with open(LOG_FILE, "w") as f:
            for r in records:
                f.write(json.dumps(r) + "\n")
                
    return updated

def get_all_logs(limit: int = 50) -> list:
    if not os.path.exists(LOG_FILE):
        return []
    with open(LOG_FILE, "r") as f:
        entries = [json.loads(line.strip()) for line in f if line.strip()]
    return entries[-limit:]
