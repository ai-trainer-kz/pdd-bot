import sqlite3

DB_NAME = "database.db"

def get_connection():
    return sqlite3.connect(DB_NAME)

def init_db():
    conn = get_connection()
    cur = conn.cursor()

    cur.execute("""
    CREATE TABLE IF NOT EXISTS users (
        user_id INTEGER PRIMARY KEY,
        name TEXT,
        score INTEGER DEFAULT 0,
        correct INTEGER DEFAULT 0,
        wrong INTEGER DEFAULT 0
    )
    """)

    conn.commit()
    conn.close()


def get_user(user_id, name="User"):
    conn = get_connection()
    cur = conn.cursor()

    cur.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
    user = cur.fetchone()

    if not user:
        cur.execute(
            "INSERT INTO users (user_id, name) VALUES (?, ?)",
            (user_id, name)
        )
        conn.commit()

    conn.close()


def update_user(user_id, correct=0, wrong=0, score=0):
    conn = get_connection()
    cur = conn.cursor()

    cur.execute("""
        UPDATE users
        SET correct = correct + ?,
            wrong = wrong + ?,
            score = score + ?
        WHERE user_id = ?
    """, (correct, wrong, score, user_id))

    conn.commit()
    conn.close()
