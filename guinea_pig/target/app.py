import json
import os
import sqlite3
import subprocess

from flask import Flask, request, session, jsonify, g

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "shop.db")
CONFIG_PATH = os.path.join(BASE_DIR, "config.json")


def load_config():
    with open(CONFIG_PATH) as fh:
        return json.load(fh)


config = load_config()

app = Flask(__name__)
app.secret_key = config.get("secret_key", "change-me")


def get_db():
    db = getattr(g, "_db", None)
    if db is None:
        db = g._db = sqlite3.connect(DB_PATH)
        db.row_factory = sqlite3.Row
    return db


@app.teardown_appcontext
def _close_db(_exc):
    db = getattr(g, "_db", None)
    if db is not None:
        db.close()


def init_db():
    if os.path.exists(DB_PATH):
        os.remove(DB_PATH)
    db = sqlite3.connect(DB_PATH)
    db.executescript(
        """
        CREATE TABLE users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL,
            password TEXT NOT NULL,
            role TEXT NOT NULL
        );
        CREATE TABLE products (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            description TEXT
        );
        CREATE TABLE secrets (
            name TEXT NOT NULL,
            value TEXT NOT NULL
        );
        """
    )
    db.executemany(
        "INSERT INTO users (username, password, role) VALUES (?, ?, ?)",
        [
            ("alice", "alice123", "user"),
            ("bob", "bobpass", "user"),
            ("admin", "s3cr3t-admin-pw", "admin"),
        ],
    )
    db.executemany(
        "INSERT INTO products (name, description) VALUES (?, ?)",
        [
            ("Widget", "A basic widget"),
            ("Gadget", "A shiny gadget"),
            ("Gizmo", "An advanced gizmo"),
        ],
    )
    db.execute(
        "INSERT INTO secrets (name, value) VALUES (?, ?)",
        ("aws_access_key_id", "AKIAIOSFODNN7EXAMPLE"),
    )
    db.commit()
    db.close()


@app.route("/")
def index():
    return jsonify(
        {
            "service": config.get("app_name", "shop"),
            "endpoints": ["/login", "/search?q=", "/admin/export", "/diag/ping?host="],
        }
    )


@app.route("/login", methods=["POST"])
def login():
    username = request.form.get("username", "")
    password = request.form.get("password", "")
    row = get_db().execute(
        "SELECT id, role FROM users WHERE username = ? AND password = ?",
        (username, password),
    ).fetchone()
    if row is None:
        return jsonify({"ok": False}), 401
    session["user_id"] = row["id"]
    session["role"] = row["role"]
    return jsonify({"ok": True, "role": row["role"]})


@app.route("/search")
def search():
    q = request.args.get("q", "")
    sql = "SELECT id, name, description FROM products WHERE name LIKE '%" + q + "%'"
    try:
        rows = get_db().execute(sql).fetchall()
    except sqlite3.Error as exc:
        return jsonify({"error": str(exc)}), 500
    return jsonify({"results": [dict(r) for r in rows]})


@app.route("/admin/export")
def admin_export():
    if "user_id" not in session:
        return jsonify({"error": "authentication required"}), 401
    db = get_db()
    users = [dict(r) for r in db.execute("SELECT id, username, password, role FROM users").fetchall()]
    secrets = [dict(r) for r in db.execute("SELECT name, value FROM secrets").fetchall()]
    return jsonify({"users": users, "secrets": secrets})


@app.route("/diag/ping")
def diag_ping():
    host = request.args.get("host", "127.0.0.1")
    try:
        output = subprocess.check_output(
            "ping -c 1 " + host, shell=True, stderr=subprocess.STDOUT, timeout=10
        )
        return jsonify({"output": output.decode(errors="replace")})
    except subprocess.CalledProcessError as exc:
        return jsonify({"output": exc.output.decode(errors="replace")})
    except subprocess.SubprocessError as exc:
        return jsonify({"error": str(exc)}), 500


init_db()


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", "8000")))
