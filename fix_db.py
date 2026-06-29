import sqlite3
import json
from pathlib import Path

DB_PATH = Path("reddit_marketing/reddit_marketing.db")

with sqlite3.connect(DB_PATH) as conn:
    c = conn.cursor()
    c.execute("SELECT name, state_json FROM projects")
    rows = c.fetchall()
    
    for name, state_json in rows:
        state = json.loads(state_json)
        drafts = state.get("drafts", [])
        changed = False
        
        for draft in drafts:
            # If the draft_type is 'reply' but the opportunity was from comment_reply
            if draft.get("draft_type") == "reply" and draft.get("opportunity", {}).get("type") == "comment_reply":
                draft["draft_type"] = "comment_reply"
                changed = True
                
        if changed:
            c.execute("UPDATE projects SET state_json = ? WHERE name = ?", (json.dumps(state), name))
            conn.commit()
            print(f"Updated DB for project: {name}")

print("Done.")
