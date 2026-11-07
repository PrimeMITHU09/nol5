import sqlite3
import os

DB_PATH = os.path.join(os.path.dirname(__file__), "bot.db")

def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA journal_mode = WAL")
    conn.execute("PRAGMA synchronous = NORMAL")
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    with get_connection() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                current_email TEXT,
                preferred_domain TEXT DEFAULT 'uqu.me',
                auto_notify INTEGER DEFAULT 1,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS saved_mails (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                email TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(user_id, email)
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS notified_emails (
                email_id TEXT PRIMARY KEY,
                user_id INTEGER,
                address TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.commit()

def get_user(user_id: int):
    with get_connection() as conn:
        cur = conn.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
        return cur.fetchone()

def create_or_update_user(user_id: int, current_email: str = None, preferred_domain: str = None, auto_notify: int = None):
    with get_connection() as conn:
        user = get_user(user_id)
        if not user:
            conn.execute(
                "INSERT INTO users (user_id, current_email, preferred_domain, auto_notify) VALUES (?, ?, ?, ?)",
                (user_id, current_email, preferred_domain or 'uqu.me', 1 if auto_notify is None else auto_notify)
            )
        else:
            fields = []
            vals = []
            if current_email is not None:
                fields.append("current_email = ?")
                vals.append(current_email)
            if preferred_domain is not None:
                fields.append("preferred_domain = ?")
                vals.append(preferred_domain)
            if auto_notify is not None:
                fields.append("auto_notify = ?")
                vals.append(auto_notify)
            if fields:
                vals.append(user_id)
                conn.execute(f"UPDATE users SET {', '.join(fields)} WHERE user_id = ?", vals)
        conn.commit()

def save_email(user_id: int, email: str) -> bool:
    with get_connection() as conn:
        try:
            conn.execute("INSERT INTO saved_mails (user_id, email) VALUES (?, ?)", (user_id, email))
            conn.commit()
            return True
        except sqlite3.IntegrityError:
            return False

def get_saved_emails(user_id: int):
    with get_connection() as conn:
        cur = conn.execute("SELECT id, email, created_at FROM saved_mails WHERE user_id = ? ORDER BY id DESC", (user_id,))
        return cur.fetchall()

def delete_saved_email(user_id: int, email: str):
    with get_connection() as conn:
        conn.execute("DELETE FROM saved_mails WHERE user_id = ? AND email = ?", (user_id, email))
        conn.commit()

def delete_all_saved_emails(user_id: int):
    with get_connection() as conn:
        conn.execute("DELETE FROM saved_mails WHERE user_id = ?", (user_id,))
        conn.commit()

def is_email_notified(email_id: str) -> bool:
    with get_connection() as conn:
        cur = conn.execute("SELECT 1 FROM notified_emails WHERE email_id = ?", (email_id,))
        return cur.fetchone() is not None

def mark_email_notified(email_id: str, user_id: int, address: str):
    with get_connection() as conn:
        conn.execute(
            "INSERT OR IGNORE INTO notified_emails (email_id, user_id, address) VALUES (?, ?, ?)",
            (email_id, user_id, address)
        )
        conn.commit()

def get_active_users():
    with get_connection() as conn:
        cur = conn.execute("SELECT user_id, current_email FROM users WHERE current_email IS NOT NULL AND current_email != '' AND auto_notify = 1")
        return cur.fetchall()

