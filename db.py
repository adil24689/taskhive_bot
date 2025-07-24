import sqlite3
from config import DB_NAME, COIN_RATE

def get_conn():
    return sqlite3.connect(DB_NAME)

def init_db():
    with get_conn() as conn, open("schema.sql") as f:
        conn.executescript(f.read())

def add_user(user_id, username, name, referred_by=None):
    with get_conn() as conn:
        cur = conn.cursor()
        if referred_by:
            cur.execute(
                "INSERT OR IGNORE INTO users (user_id, username, name, referred_by, points) VALUES (?, ?, ?, ?, 500)",
                (user_id, username, name, referred_by)
            )
            # Referrer gets 200 points bonus
            cur.execute("UPDATE users SET points = points + 200 WHERE user_id = ?", (referred_by,))
        else:
            cur.execute(
                "INSERT OR IGNORE INTO users (user_id, username, name, points) VALUES (?, ?, ?, 200)",
                (user_id, username, name)
            )
        conn.commit()

def get_user(user_id):
    with get_conn() as conn:
        return conn.execute("SELECT * FROM users WHERE user_id = ?", (user_id,)).fetchone()

def update_points(user_id, amount):
    with get_conn() as conn:
        conn.execute("UPDATE users SET points = points + ? WHERE user_id = ?", (amount, user_id))
        conn.commit()

def update_earnings(user_id, amount):
    with get_conn() as conn:
        conn.execute("UPDATE users SET earnings = earnings + ? WHERE user_id = ?", (amount, user_id))
        conn.commit()

def create_task(user_id, task_type, title, desc, proof, total, reward):
    with get_conn() as conn:
        conn.execute("""
            INSERT INTO tasks (user_id, task_type, title, description, proof_type, total_workers, reward)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (user_id, task_type, title, desc, proof, total, reward))
        conn.commit()

def get_active_tasks():
    with get_conn() as conn:
        return conn.execute("SELECT * FROM tasks WHERE is_hidden = 0 AND completed < total_workers").fetchall()

def submit_task(task_id, worker_id, proof):
    with get_conn() as conn:
        conn.execute("INSERT INTO submissions (task_id, worker_id, proof) VALUES (?, ?, ?)", (task_id, worker_id, proof))
        conn.commit()

def get_submissions(status='pending'):
    with get_conn() as conn:
        return conn.execute("SELECT * FROM submissions WHERE status = ?", (status,)).fetchall()

def review_submission(submission_id, approve=True):
    with get_conn() as conn:
        sub = conn.execute("SELECT * FROM submissions WHERE submission_id = ?", (submission_id,)).fetchone()
        if not sub:
            return
        task = conn.execute("SELECT * FROM tasks WHERE task_id = ?", (sub[1],)).fetchone()
        if not task:
            return
        reward = task[8]  # reward column index in tasks
        worker_id = sub[2]
        conn.execute(
            "UPDATE submissions SET status = ? WHERE submission_id = ?",
            ("approved" if approve else "rejected", submission_id)
        )
        if approve:
            conn.execute("UPDATE tasks SET completed = completed + 1 WHERE task_id = ?", (task[0],))
            points_awarded = int(reward * 0.9)  # 90% reward to worker
            conn.execute("UPDATE users SET points = points + ? WHERE user_id = ?", (points_awarded, worker_id))
            conn.execute("UPDATE users SET earnings = earnings + ? WHERE user_id = ?", (points_awarded, worker_id))
        conn.commit()

def log_recharge(user_id, amount, method, trx_id):
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO recharges (user_id, amount, method, trx_id) VALUES (?, ?, ?, ?)",
            (user_id, amount, method, trx_id)
        )
        conn.commit()

def get_pending_recharges():
    with get_conn() as conn:
        return conn.execute("SELECT * FROM recharges WHERE verified = 0").fetchall()

def verify_recharge(recharge_id):
    with get_conn() as conn:
        r = conn.execute("SELECT * FROM recharges WHERE recharge_id = ?", (recharge_id,)).fetchone()
        if r:
            # r = (recharge_id, user_id, amount, method, trx_id, verified, ...)
            user_id = r[1]
            amount = r[2]
            conn.execute("UPDATE users SET points = points + ? WHERE user_id = ?", (amount * COIN_RATE, user_id))
            conn.execute("UPDATE recharges SET verified = 1 WHERE recharge_id = ?", (recharge_id,))
            conn.commit()

def request_withdraw(user_id, amount, method, number):
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO withdrawals (user_id, amount, method, number) VALUES (?, ?, ?, ?)",
            (user_id, amount, method, number)
        )
        conn.commit()

def get_pending_withdrawals():
    with get_conn() as conn:
        return conn.execute("SELECT * FROM withdrawals WHERE verified = 0").fetchall()

def verify_withdraw(withdrawal_id):
    with get_conn() as conn:
        w = conn.execute("SELECT * FROM withdrawals WHERE withdrawal_id = ?", (withdrawal_id,)).fetchone()
        if w:
            conn.execute("UPDATE withdrawals SET verified = 1 WHERE withdrawal_id = ?", (withdrawal_id,))
            conn.commit()


def deduct_points(user_id, amount):
    with get_conn() as conn:
        conn.execute("UPDATE users SET points = points - ? WHERE user_id = ?", (amount, user_id))
        conn.commit()

from db import init_db

if __name__ == "__main__":
    init_db()
    print("Database initialized successfully!")
