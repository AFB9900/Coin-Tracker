import sqlite3
from core.config import DB_FILE

def get_db_connection():
    conn = sqlite3.connect(DB_FILE, check_same_thread=False)
    conn.row_factory = sqlite3.Row  # Sütunlara isimleriyle erişim sağlar
    return conn