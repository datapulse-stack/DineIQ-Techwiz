"""
Authentication, roles and audit trail for DineIQ Analytics.

Small, dependency-light: SQLite for storage (no server to run) and Werkzeug for
password hashing (never store plain passwords). Three roles with a simple
permission model:

    Admin    -> view + export + manage users + see the audit log
    Manager  -> view + export
    Analyst  -> view only   (the default a new signup lands on)

The idea: anyone can sign up, but they start as an Analyst with read-only access
until an Admin upgrades them.
"""
import sqlite3
import secrets
from pathlib import Path
from datetime import datetime
from werkzeug.security import generate_password_hash, check_password_hash

ROOT = Path(__file__).resolve().parent
DB_DIR = ROOT / "database"
DB_DIR.mkdir(exist_ok=True)
DB_PATH = DB_DIR / "dineiq.db"
SECRET_PATH = DB_DIR / "secret.key"

ROLES = ["Admin", "Manager", "Analyst"]
PERMISSIONS = {
    "Admin":   {"view", "export", "admin"},
    "Manager": {"view", "export"},
    "Analyst": {"view"},
}


def get_secret_key():
    """persist a random session key so logins survive restarts."""
    if SECRET_PATH.exists():
        return SECRET_PATH.read_text().strip()
    key = secrets.token_hex(32)
    SECRET_PATH.write_text(key)
    return key


def _conn():
    c = sqlite3.connect(DB_PATH)
    c.row_factory = sqlite3.Row
    return c


def init_db():
    with _conn() as c:
        c.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                email TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                role TEXT NOT NULL DEFAULT 'Analyst',
                active INTEGER NOT NULL DEFAULT 1,
                created_at TEXT NOT NULL
            )""")
        c.execute("""
            CREATE TABLE IF NOT EXISTS audit_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ts TEXT NOT NULL,
                user_email TEXT,
                action TEXT NOT NULL,
                detail TEXT,
                ip TEXT
            )""")
    _seed_admin()


def _seed_admin():
    """create a default admin the first time so you can actually get in."""
    with _conn() as c:
        n = c.execute("SELECT COUNT(*) FROM users").fetchone()[0]
        if n == 0:
            c.execute(
                "INSERT INTO users (name,email,password_hash,role,active,created_at) "
                "VALUES (?,?,?,?,1,?)",
                ("Restaurant Owner", "admin@dineiq.local",
                 generate_password_hash("admin123"), "Admin",
                 datetime.now().isoformat(timespec="seconds")))
            print("[auth] seeded default admin -> admin@dineiq.local / admin123 "
                  "(please change this)")


# ---- user ops ------------------------------------------------------------
def create_user(name, email, password, role="Analyst"):
    email = email.strip().lower()
    if role not in ROLES:
        role = "Analyst"
    try:
        with _conn() as c:
            c.execute(
                "INSERT INTO users (name,email,password_hash,role,active,created_at) "
                "VALUES (?,?,?,?,1,?)",
                (name.strip(), email, generate_password_hash(password), role,
                 datetime.now().isoformat(timespec="seconds")))
        return True, "Account created"
    except sqlite3.IntegrityError:
        return False, "An account with that email already exists"


def authenticate(email, password):
    email = email.strip().lower()
    with _conn() as c:
        row = c.execute("SELECT * FROM users WHERE email=?", (email,)).fetchone()
    if row and row["active"] and check_password_hash(row["password_hash"], password):
        return dict(row)
    return None


def get_user(uid):
    with _conn() as c:
        row = c.execute("SELECT * FROM users WHERE id=?", (uid,)).fetchone()
    return dict(row) if row else None


def list_users():
    with _conn() as c:
        return [dict(r) for r in c.execute(
            "SELECT id,name,email,role,active,created_at FROM users ORDER BY id").fetchall()]


def set_role(uid, role):
    if role in ROLES:
        with _conn() as c:
            c.execute("UPDATE users SET role=? WHERE id=?", (role, uid))


def set_active(uid, active):
    with _conn() as c:
        c.execute("UPDATE users SET active=? WHERE id=?", (1 if active else 0, uid))


def email_exists(email):
    email = email.strip().lower()
    with _conn() as c:
        row = c.execute("SELECT id FROM users WHERE email=?", (email,)).fetchone()
    return row is not None


def set_password(email, new_password):
    """reset a user's password by email (used by the forgot-password flow).
    returns True if a matching account was updated."""
    email = email.strip().lower()
    with _conn() as c:
        row = c.execute("SELECT id FROM users WHERE email=?", (email,)).fetchone()
        if not row:
            return False
        c.execute("UPDATE users SET password_hash=? WHERE id=?",
                  (generate_password_hash(new_password), row["id"]))
    return True


def count_users():
    with _conn() as c:
        return c.execute("SELECT COUNT(*) FROM users").fetchone()[0]


# ---- audit ---------------------------------------------------------------
def log(action, detail="", email=None, ip=None):
    with _conn() as c:
        c.execute("INSERT INTO audit_log (ts,user_email,action,detail,ip) VALUES (?,?,?,?,?)",
                  (datetime.now().isoformat(timespec="seconds"), email, action, detail, ip))


def recent_audit(limit=100):
    with _conn() as c:
        return [dict(r) for r in c.execute(
            "SELECT * FROM audit_log ORDER BY id DESC LIMIT ?", (limit,)).fetchall()]


def can(role, permission):
    return permission in PERMISSIONS.get(role, set())
