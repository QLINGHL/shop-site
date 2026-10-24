# 小店后端: 用户注册/登录(JWT) + 订单, SQLite
# 部署目标: AlwaysData 免费版 Python WSGI 站点 (见 wsgi.py / DEPLOY.md)
# 约定: 密码 bcrypt, 登录态 JWT(30天), 限流防爆破(呼应他"怕被同行攻击"的要求)
import os
import re
import sqlite3
import time
from datetime import datetime, timedelta, timezone
from functools import wraps

import bcrypt
import jwt
from flask import Flask, request, jsonify, g
from flask_cors import CORS

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.environ.get("SHOP_DB", os.path.join(BASE_DIR, "shop.db"))
JWT_SECRET = os.environ.get("JWT_SECRET", "")
FRONTEND_ORIGIN = os.environ.get("FRONTEND_ORIGIN", "https://qlinghl.alwaysdata.net")
JWT_DAYS = 30

app = Flask(__name__)
CORS(app, origins=[FRONTEND_ORIGIN])

USERNAME_RE = re.compile(r"^[A-Za-z0-9_.\-@]{3,32}$")


def db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    with db() as c:
        c.execute(
            """CREATE TABLE IF NOT EXISTS users(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                created_at TEXT NOT NULL)"""
        )
        c.execute(
            """CREATE TABLE IF NOT EXISTS orders(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                product_sku TEXT NOT NULL,
                contact TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'pending',
                ji8_order_id TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                FOREIGN KEY(user_id) REFERENCES users(id))"""
        )


init_db()


# ---- 简易限流: 单进程内存版, 每个 IP 每 60 秒最多 N 次 ----
# 重启后计数清零; 这点流量下够用, 被刷时至少爆破和批量下单会被挡
_hits = {}


def rate_limited(limit=10, window=60):
    def deco(fn):
        @wraps(fn)
        def wrapper(*a, **kw):
            ip = (
                request.headers.get("X-Forwarded-For", request.remote_addr or "?")
                .split(",")[0]
                .strip()
            )
            key = (fn.__name__, ip)
            now = time.time()
            lst = [t for t in _hits.get(key, []) if now - t < window]
            if len(lst) >= limit:
                return jsonify({"ok": False, "error": "too_many_requests"}), 429
            lst.append(now)
            _hits[key] = lst
            return fn(*a, **kw)

        return wrapper

    return deco


def make_token(uid):
    if not JWT_SECRET:
        raise RuntimeError("JWT_SECRET 环境变量未设置")
    payload = {
        "uid": uid,
        "exp": datetime.now(timezone.utc) + timedelta(days=JWT_DAYS),
    }
    return jwt.encode(payload, JWT_SECRET, algorithm="HS256")


def auth_required(fn):
    @wraps(fn)
    def wrapper(*a, **kw):
        h = request.headers.get("Authorization", "")
        if not h.startswith("Bearer "):
            return jsonify({"ok": False, "error": "unauthorized"}), 401
        try:
            data = jwt.decode(h[7:], JWT_SECRET, algorithms=["HS256"])
        except Exception:
            return jsonify({"ok": False, "error": "unauthorized"}), 401
        g.uid = data["uid"]
        return fn(*a, **kw)

    return wrapper


@app.get("/api/health")
def health():
    return jsonify({"ok": True})


@app.post("/api/register")
@rate_limited(10, 60)
def register():
    body = request.get_json(force=True, silent=True) or {}
    username = (body.get("username") or "").strip()
    password = body.get("password") or ""
    if not USERNAME_RE.match(username):
        return jsonify({"ok": False, "error": "用户名 3-32 位, 仅字母数字 _ . - @"}), 400
    if len(password) < 6:
        return jsonify({"ok": False, "error": "密码至少 6 位"}), 400
    ph = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()
    now = datetime.now(timezone.utc).isoformat()
    try:
        with db() as c:
            cur = c.execute(
                "INSERT INTO users(username,password_hash,created_at) VALUES(?,?,?)",
                (username, ph, now),
            )
            uid = cur.lastrowid
    except sqlite3.IntegrityError:
        return jsonify({"ok": False, "error": "用户名已被占用"}), 409
    return jsonify({"ok": True, "token": make_token(uid)})


@app.post("/api/login")
@rate_limited(10, 60)
def login():
    body = request.get_json(force=True, silent=True) or {}
    username = (body.get("username") or "").strip()
    password = body.get("password") or ""
    with db() as c:
        row = c.execute(
            "SELECT id, password_hash FROM users WHERE username=?", (username,)
        ).fetchone()
    if not row or not bcrypt.checkpw(
        password.encode(), row["password_hash"].encode()
    ):
        # 用户名/密码错误回一样的文案, 不泄露"用户名是否存在"
        return jsonify({"ok": False, "error": "用户名或密码错误"}), 401
    return jsonify({"ok": True, "token": make_token(row["id"])})


@app.post("/api/orders")
@auth_required
@rate_limited(30, 60)
def create_order():
    body = request.get_json(force=True, silent=True) or {}
    sku = (body.get("product_sku") or "").strip()[:64]
    contact = (body.get("contact") or "").strip()[:128]
    if not sku or not contact:
        return jsonify({"ok": False, "error": "缺少商品或联系方式"}), 400
    now = datetime.now(timezone.utc).isoformat()
    with db() as c:
        cur = c.execute(
            "INSERT INTO orders(user_id,product_sku,contact,status,created_at,updated_at)"
            " VALUES(?,?,?,?,?,?)",
            (g.uid, sku, contact, "pending", now, now),
        )
        oid = cur.lastrowid
    # 注意: 付款成功后才调 ji8 发货; 文档到之前这里只落库, 不发货
    return jsonify({"ok": True, "order_id": oid, "status": "pending"})


@app.get("/api/orders")
@auth_required
def list_orders():
    with db() as c:
        rows = c.execute(
            "SELECT id,product_sku,contact,status,created_at FROM orders"
            " WHERE user_id=? ORDER BY id DESC LIMIT 50",
            (g.uid,),
        ).fetchall()
    return jsonify({"ok": True, "orders": [dict(r) for r in rows]})


if __name__ == "__main__":
    # 仅本地调试用; 线上走 wsgi.py
    app.run(host="127.0.0.1", port=5000)
