import sqlite3
import hmac
import hashlib
from fastapi import Request, HTTPException
from passlib.context import CryptContext
from passlib.exc import UnknownHashError
from core.config import DB_FILE, SESSION_COOKIE_NAME, SESSION_SECRET

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def get_user_by_username(username: str):
    conn = sqlite3.connect(DB_FILE, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("SELECT id, username, password_hash, telegram_token, telegram_chat_id FROM users WHERE username = ?", (username.strip(),))
    row = cursor.fetchone()
    conn.close()
    if row:
        return dict(row)
    return None


def make_session_cookie(username: str) -> str:
    username = username.strip()
    signature = hmac.new(SESSION_SECRET.encode(), username.encode(), hashlib.sha256).hexdigest()
    return f"{username}|{signature}"


def verify_session_cookie(cookie_value: str):
    if not cookie_value or "|" not in cookie_value:
        return None
    username, signature = cookie_value.split("|", 1)
    expected = hmac.new(SESSION_SECRET.encode(), username.encode(), hashlib.sha256).hexdigest()
    if hmac.compare_digest(expected, signature):
        return username
    return None


def get_current_user(request: Request):
    cookie_value = request.cookies.get(SESSION_COOKIE_NAME)
    username = verify_session_cookie(cookie_value)
    if not username:
        raise HTTPException(status_code=303, detail="Oturum bulunamadı")
    user = get_user_by_username(username)
    if not user:
        raise HTTPException(status_code=303, detail="Geçersiz oturum")
    return user


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    try:
        return pwd_context.verify(plain_password, hashed_password)
    except UnknownHashError:
        # Önceki SHA-256 base hash'lerini de destekleyelim
        legacy_salt = "kgm_yilgar_gokboru_2026"
        legacy_hash = hashlib.sha256((plain_password + legacy_salt).encode('utf-8')).hexdigest()
        return legacy_hash == hashed_password
