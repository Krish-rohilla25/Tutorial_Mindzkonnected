import sqlite3
import json
from pathlib import Path
from datetime import datetime

DB_PATH = Path(__file__).resolve().parent / "reddit_marketing.db"

def get_connection():
    return sqlite3.connect(DB_PATH)

def init_db():
    with get_connection() as conn:
        c = conn.cursor()
        c.execute('''
            CREATE TABLE IF NOT EXISTS projects (
                name TEXT PRIMARY KEY,
                brief_json TEXT,
                state_json TEXT,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        c.execute('''
            CREATE TABLE IF NOT EXISTS published_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                project_name TEXT,
                url TEXT,
                content TEXT,
                draft_type TEXT,
                subreddit TEXT,
                published_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        conn.commit()


def save_project(name: str, brief_dict: dict, state_dict: dict):
    with get_connection() as conn:
        c = conn.cursor()
        c.execute('''
            INSERT INTO projects (name, brief_json, state_json, updated_at)
            VALUES (?, ?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(name) DO UPDATE SET
                brief_json=excluded.brief_json,
                state_json=excluded.state_json,
                updated_at=CURRENT_TIMESTAMP
        ''', (name, json.dumps(brief_dict), json.dumps(state_dict)))
        conn.commit()


def load_project(name: str):
    with get_connection() as conn:
        c = conn.cursor()
        c.execute('SELECT brief_json, state_json FROM projects WHERE name = ?', (name,))
        row = c.fetchone()
        if row:
            return json.loads(row[0]), json.loads(row[1])
        return None, None


def get_all_projects():
    with get_connection() as conn:
        c = conn.cursor()
        c.execute('SELECT name FROM projects ORDER BY updated_at DESC')
        return [row[0] for row in c.fetchall()]


def log_published(project_name: str, url: str, content: str, draft_type: str, subreddit: str):
    with get_connection() as conn:
        c = conn.cursor()
        c.execute('''
            INSERT INTO published_log (project_name, url, content, draft_type, subreddit)
            VALUES (?, ?, ?, ?, ?)
        ''', (project_name, url, content, draft_type, subreddit))
        conn.commit()


def get_published_log(project_name: str = None):
    with get_connection() as conn:
        conn.row_factory = sqlite3.Row
        c = conn.cursor()
        if project_name:
            c.execute('SELECT * FROM published_log WHERE project_name = ? ORDER BY published_at DESC', (project_name,))
        else:
            c.execute('SELECT * FROM published_log ORDER BY published_at DESC')
        return [dict(row) for row in c.fetchall()]
