import os
import sqlite3
import hashlib
import secrets
from datetime import datetime
from typing import Optional, Any, Dict, List

from python.helpers import dotenv

ROLE_ADMIN = "admin"
ROLE_USER = "user"
DB_PATH = os.path.join("tmp", "users.db")


def _get_conn():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def _hash_password(password: str, salt: Optional[str] = None) -> tuple[str, str]:
    if not salt:
        salt = secrets.token_hex(16)
    h = hashlib.sha256((salt + password).encode()).hexdigest()
    return h, salt


def initialize_database():
    with _get_conn() as conn:
        cur = conn.cursor()
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                salt TEXT NOT NULL,
                role TEXT NOT NULL CHECK(role IN ('admin','user')),
                created_at TEXT NOT NULL,
                created_by TEXT,
                last_login TEXT
            )
            """
        )
        conn.commit()

        # Create default admin if none exists
        cur.execute("SELECT COUNT(*) AS c FROM users")
        count = cur.fetchone()[0]
        if count == 0:
            admin_user = dotenv.get_dotenv_value("AUTH_LOGIN") or "admin"
            admin_pass = dotenv.get_dotenv_value("AUTH_PASSWORD") or "changeme"
            ph, salt = _hash_password(admin_pass)
            cur.execute(
                """
                INSERT INTO users (username, password_hash, salt, role, created_at, created_by)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    admin_user,
                    ph,
                    salt,
                    ROLE_ADMIN,
                    datetime.utcnow().isoformat(),
                    "system",
                ),
            )
            conn.commit()


def create_user(username: str, password: str, role: str, created_by: str) -> Dict[str, Any]:
    if not username or not password:
        raise ValueError("Le nom d'utilisateur et le mot de passe sont requis")
    if role not in (ROLE_ADMIN, ROLE_USER):
        raise ValueError("Rôle invalide (admin/user)")

    with _get_conn() as conn:
        cur = conn.cursor()
        # ensure unique
        cur.execute("SELECT 1 FROM users WHERE username=?", (username,))
        if cur.fetchone():
            raise ValueError("Nom d'utilisateur déjà utilisé")
        ph, salt = _hash_password(password)
        cur.execute(
            """
            INSERT INTO users (username, password_hash, salt, role, created_at, created_by)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (username, ph, salt, role, datetime.utcnow().isoformat(), created_by),
        )
        conn.commit()
        return get_user_by_username(username)  # type: ignore


def authenticate_user(username: str, password: str) -> Optional[Dict[str, Any]]:
    with _get_conn() as conn:
        cur = conn.cursor()
        cur.execute("SELECT * FROM users WHERE username=?", (username,))
        row = cur.fetchone()
        if not row:
            return None
        expected_hash = row["password_hash"]
        salt = row["salt"]
        got_hash, _ = _hash_password(password, salt)
        if got_hash != expected_hash:
            return None
        return dict(row)


def get_user_by_username(username: str) -> Optional[Dict[str, Any]]:
    with _get_conn() as conn:
        cur = conn.cursor()
        cur.execute("SELECT id, username, role, created_at, created_by, last_login FROM users WHERE username=?", (username,))
        row = cur.fetchone()
        return dict(row) if row else None


def get_all_users() -> List[Dict[str, Any]]:
    with _get_conn() as conn:
        cur = conn.cursor()
        cur.execute("SELECT id, username, role, created_at, created_by, last_login FROM users ORDER BY username ASC")
        rows = cur.fetchall()
        return [dict(r) for r in rows]


def update_user(user_id: int, **kwargs) -> Dict[str, Any]:
    allowed = {"password", "role"}
    updates = {k: v for k, v in kwargs.items() if k in allowed and v is not None}
    if not updates:
        raise ValueError("Aucune mise à jour spécifiée")

    with _get_conn() as conn:
        cur = conn.cursor()
        if "password" in updates:
            ph, salt = _hash_password(updates.pop("password"))
            cur.execute("UPDATE users SET password_hash=?, salt=? WHERE id=?", (ph, salt, user_id))
        if "role" in updates:
            role = updates["role"]
            if role not in (ROLE_ADMIN, ROLE_USER):
                raise ValueError("Rôle invalide (admin/user)")
            cur.execute("UPDATE users SET role=? WHERE id=?", (role, user_id))
        conn.commit()
        cur.execute("SELECT id, username, role, created_at, created_by, last_login FROM users WHERE id=?", (user_id,))
        row = cur.fetchone()
        if not row:
            raise ValueError("Utilisateur introuvable")
        return dict(row)


def _count_admins(conn) -> int:
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM users WHERE role='admin'")
    return int(cur.fetchone()[0])


def delete_user(user_id: int) -> None:
    with _get_conn() as conn:
        cur = conn.cursor()
        # check if admin and last one
        cur.execute("SELECT role FROM users WHERE id=?", (user_id,))
        row = cur.fetchone()
        if not row:
            raise ValueError("Utilisateur introuvable")
        if row["role"] == ROLE_ADMIN:
            if _count_admins(conn) <= 1:
                raise ValueError("Impossible de supprimer le dernier administrateur")
        cur.execute("DELETE FROM users WHERE id=?", (user_id,))
        conn.commit()


def update_last_login(user_id: int) -> None:
    with _get_conn() as conn:
        conn.execute(
            "UPDATE users SET last_login=? WHERE id=?",
            (datetime.utcnow().isoformat(), user_id),
        )
        conn.commit()


def is_admin(username: str) -> bool:
    with _get_conn() as conn:
        cur = conn.cursor()
        cur.execute("SELECT role FROM users WHERE username=?", (username,))
        row = cur.fetchone()
        return bool(row and row["role"] == ROLE_ADMIN)


def get_user_role(username: str) -> Optional[str]:
    with _get_conn() as conn:
        cur = conn.cursor()
        cur.execute("SELECT role FROM users WHERE username=?", (username,))
        row = cur.fetchone()
        return row["role"] if row else None
