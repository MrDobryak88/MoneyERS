import sqlite3
import bcrypt
from contextlib import contextmanager
from datetime import datetime
from typing import Dict, Optional, Tuple, List


@contextmanager
def get_db_connection():
    """Context manager for database connections."""
    conn = sqlite3.connect('exchange.db')
    try:
        yield conn
    finally:
        conn.close()


def init_db():
    """Initializes the database with necessary tables."""
    with get_db_connection() as conn:
        c = conn.cursor()
        c.executescript('''
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                password_hash BLOB NOT NULL,
                created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS transactions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                from_currency TEXT NOT NULL,
                to_currency TEXT NOT NULL,
                amount REAL NOT NULL,
                rate REAL NOT NULL,
                timestamp TEXT NOT NULL,
                FOREIGN KEY (user_id) REFERENCES users(id)
            );
            CREATE TABLE IF NOT EXISTS settings (
                user_id INTEGER NOT NULL,
                key TEXT NOT NULL,
                value TEXT NOT NULL,
                PRIMARY KEY (user_id, key),
                FOREIGN KEY (user_id) REFERENCES users(id)
            );
            CREATE TABLE IF NOT EXISTS historical_rates (
                date TEXT NOT NULL,
                currency TEXT NOT NULL,
                rate REAL NOT NULL,
                PRIMARY KEY (date, currency)
            );
        ''')
        conn.commit()


def add_user(username: str, password: str) -> bool:
    """Adds a new user with hashed password."""
    password_hash = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt())
    created_at = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    with get_db_connection() as conn:
        c = conn.cursor()
        try:
            c.execute("INSERT INTO users (username, password_hash, created_at) VALUES (?, ?, ?)",
                      (username, password_hash, created_at))
            conn.commit()
            return True
        except sqlite3.IntegrityError:
            return False


def check_login(username: str, password: str) -> Optional[int]:
    """Verifies user credentials."""
    with get_db_connection() as conn:
        c = conn.cursor()
        c.execute("SELECT id, password_hash FROM users WHERE username = ?", (username,))
        result = c.fetchone()
        if result and bcrypt.checkpw(password.encode('utf-8'), result[1]):
            return result[0]
        return None


def update_user_password(user_id: int, new_password: str) -> None:
    """Updates the user's password."""
    password_hash = bcrypt.hashpw(new_password.encode('utf-8'), bcrypt.gensalt())
    with get_db_connection() as conn:
        c = conn.cursor()
        c.execute("UPDATE users SET password_hash = ? WHERE id = ?", (password_hash, user_id))
        conn.commit()


def insert_historical_rate(date: str, currency: str, rate: float) -> None:
    """Inserts or updates a historical exchange rate."""
    with get_db_connection() as conn:
        c = conn.cursor()
        c.execute("INSERT OR REPLACE INTO historical_rates (date, currency, rate) VALUES (?, ?, ?)",
                  (date, currency, rate))
        conn.commit()


def get_historical_rates(currency: str, start_date: str, end_date: str) -> Dict[str, float]:
    """Retrieves historical exchange rates."""
    with get_db_connection() as conn:
        c = conn.cursor()
        c.execute("SELECT date, rate FROM historical_rates WHERE currency = ? AND date BETWEEN ? AND ? ORDER BY date",
                  (currency, start_date, end_date))
        return dict(c.fetchall())


def get_user_creation_date(user_id: int) -> str:
    """Возвращает дату регистрации пользователя или 'Неизвестно'."""
    with get_db_connection() as conn:
        c = conn.cursor()
        c.execute("SELECT created_at FROM users WHERE id = ?", (user_id,))
        result = c.fetchone()
        return result[0] if result else "Неизвестно"

def get_user_transactions(user_id: int, from_currency: Optional[str] = None, to_currency: Optional[str] = None,
                          start_date: Optional[datetime] = None, end_date: Optional[datetime] = None,
                          limit: Optional[int] = None) -> List[Tuple[str, str, float, float, str]]:
    """Gets user transactions with optional filters."""
    query = "SELECT from_currency, to_currency, amount, rate, timestamp FROM transactions WHERE user_id = ?"
    params = [user_id]

    if from_currency and to_currency:
        query += " AND from_currency = ? AND to_currency = ?"
        params.extend([from_currency, to_currency])
    if start_date and end_date:
        query += " AND timestamp >= ? AND timestamp <= ?"
        params.extend([start_date.strftime('%Y-%m-%d %H:%M:%S'), end_date.strftime('%Y-%m-%d %H:%M:%S')])

    query += " ORDER BY timestamp DESC"
    if limit:
        query += " LIMIT ?"
        params.append(limit)

    with get_db_connection() as conn:
        c = conn.cursor()
        c.execute(query, params)
        return c.fetchall()


def get_user_creation_date(user_id: int) -> str:
    """Gets the user's account creation date."""
    with get_db_connection() as conn:
        c = conn.cursor()
        c.execute("SELECT created_at FROM users WHERE id = ?", (user_id,))
        result = c.fetchone()
        return result[0] if result else "Неизвестно"
def get_user_stats(user_id: int) -> Tuple[int, float]:
    """Gets user transaction statistics."""
    with get_db_connection() as conn:
        c = conn.cursor()
        c.execute("SELECT COUNT(*), COALESCE(SUM(amount), 0) FROM transactions WHERE user_id = ?", (user_id,))
        return c.fetchone()