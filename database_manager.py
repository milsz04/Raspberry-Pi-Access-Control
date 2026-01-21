import sqlite3
from datetime import datetime

DB_FILE = "/home/pi/tests/project/project_database.db"

class DatabaseManager:
    # def __init__(self, db_name="~/tests/Project/project_database.db"):
    def __init__(self):
        self.db_name = DB_FILE
        self.init_db()

    def get_connection(self):
        return sqlite3.connect(self.db_name)

    def init_db(self):
        with self.get_connection() as conn:
            cursor = conn.cursor()
        
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS users (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    card_uid TEXT UNIQUE NOT NULL,
                    name TEXT NOT NULL
                )
            ''')
            
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS access_logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                    card_uid TEXT NOT NULL,
                    granted BOOLEAN NOT NULL,
                    photo_path TEXT
                )
            ''')
            conn.commit()

    def add_user(self, card_uid, name):
        with self.get_connection() as conn:
            user=conn.execute("SELECT id FROM users WHERE card_uid = ?", (card_uid,)).fetchone()
            
            if user:
                print(f"UID already in db")
                return
            
            conn.execute("INSERT INTO users (card_uid, name) VALUES (?, ?)", (card_uid, name))
            conn.commit()
            print(f"user added: {name}")

    def remove_user(self, card_uid):
        with self.get_connection() as conn:
            conn.execute("DELETE FROM users WHERE card_uid = ?", (card_uid,))

    def get_all_users(self):
        with self.get_connection() as conn:
            return conn.execute("SELECT card_uid, name FROM users").fetchall()

    def check_access(self, card_uid):
        with self.get_connection() as conn:
            user = conn.execute("SELECT name FROM users WHERE card_uid = ?",(card_uid,)).fetchone()
            return user is not None

    def log_attempt(self, card_uid, granted, photo_path=None):
        with self.get_connection() as conn:
            conn.execute('''
                INSERT INTO access_logs (card_uid, granted, photo_path) 
                VALUES (?, ?, ?)
            ''', (card_uid, granted, photo_path))

    def get_logs(self):
        with self.get_connection() as conn:
            return conn.execute("SELECT * FROM access_logs ORDER BY timestamp DESC").fetchall()

if __name__ == "__main__":
    db = DatabaseManager()
    db.add_user("4AA7744FD6", "Matesz Stankiewicz")
    # print("logs:", db.get_logs())