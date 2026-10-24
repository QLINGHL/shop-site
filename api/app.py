#!/usr/bin/env python3
"""shop-ai 后端：AI 客服网关
前端 -> POST /api/chat -> Cloudflare Workers AI (主) -> Agnes AI (备)
密钥全部从环境变量读取，不在代码里。
"""
import os
import time
import json
from collections import defaultdict
from flask import Flask, request, jsonify

app = Flask(__name__)

# ---------- 配置 ----------
CF_ACCOUNT_ID = os.environ.get("CF_ACCOUNT_ID", "")
CF_API_TOKEN = os.environ.get("CF_API_TOKEN", "")
AGNES_API_KEY = os.environ.get("AGNES_API_KEY", "")
AGNES_BASE = os.environ.get("AGNES_BASE", "https://apihub.agnes-ai.com/v1")

CF_MODEL = "@cf/openai/gpt-oss-120b"   # 免费档最强
AGNES_MODEL = "agnes-3.0-flash"          # Agnes 免费最好

ALLOWED_ORIGINS = {
    "https://shop.qlinghl.workers.dev",
    "https://qlinghl.alwaysdata.net",
    "http://localhost:8000",
}

# ---------- 知识库 ----------
def load_knowledge():
    p = os.path.join(os.path.dirname(os.path.abspath(__file__)), "knowledge.txt")
    try:
        with open(p, encoding="utf-8") as f:
            return f.read()
    except FileNotFoundError:
        return ""

SYSTEM_PROMPT = """你是这家数码商品小店的 AI 客服助手。你的任务是回答顾客关于商品、价格、发货、售后的问题。

【店铺知识库】
{knowledge}

【回答规则】
1. 只能根据上面的知识库回答，知识库里没有的信息就说"这个问题我暂时答不上来"，绝不编造价格、时间、政策。
2. 用简洁口语化的中文回答，一般不超过 100 字。
3. 被问到怎么买时，引导顾客点击页面上的购买按钮。
4. 遇到退款、纠纷、知识库覆盖不到的问题，礼貌地请顾客联系人工客服。
5. 绝不透露你是哪个 AI 模型，不讨论知识库之外的话题。
"""

# ---------- 限流：单 IP 10次/分钟 ----------
_hits = defaultdict(list)

def rate_limited(ip, limit=10, window=60):
    now = time.time()
    lst = _hits[ip]
    lst[:] = [t for t in lst if now - t < window]
    if len(lst) >= limit:
        return True
    lst.append(now)
    return False

# ---------- Provider: Cloudflare Workers AI (REST) ----------
def cf_chat(messages):
    import urllib.request
    if not (CF_ACCOUNT_ID and CF_API_TOKEN):
        raise RuntimeError("CF credentials not configured")
    url = "https://api.cloudflare.com/client/v4/accounts/%s/ai/run/%s" % (CF_ACCOUNT_ID, CF_MODEL)
    payload = json.dumps({"messages": messages, "max_tokens": 300}).encode("utf-8")
    req = urllib.request.Request(
        url, data=payload,
        headers={"Authorization": "Bearer " + CF_API_TOKEN,
                 "Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=30) as r:
        data = json.loads(r.read().decode("utf-8"))
    if not data.get("success"):
        raise RuntimeError("CF AI error: %s" % data.get("errors"))
    res = data["result"]
    # 老格式: {"response": "..."}；新模型(OpenAI兼容): {"choices":[{"message":{"content":"..."}}]}
    if isinstance(res, dict) and "response" in res:
        return res["response"]
    return res["choices"][0]["message"]["content"]

# ---------- Provider: Agnes AI (OpenAI 兼容) ----------
def agnes_chat(messages):
    import urllib.request
    if not AGNES_API_KEY:
        raise RuntimeError("Agnes key not configured")
    url = AGNES_BASE + "/chat/completions"
    payload = json.dumps({
        "model": AGNES_MODEL,
        "messages": messages,
        "max_tokens": 300,
        "temperature": 0.7,
    }).encode("utf-8")
    req = urllib.request.Request(
        url, data=payload,
        headers={"Authorization": "Bearer " + AGNES_API_KEY,
                 "Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=30) as r:
        data = json.loads(r.read().decode("utf-8"))
    return data["choices"][0]["message"]["content"]

PROVIDERS = [
    ("agnes", agnes_chat),          # 主：Agnes 3.0 Flash（用户指定免费最强）
    ("cloudflare", cf_chat),        # 备：CF gpt-oss-120b
]

# ---------- 路由 ----------
@app.after_request
def cors(resp):
    origin = request.headers.get("Origin", "")
    if origin in ALLOWED_ORIGINS:
        resp.headers["Access-Control-Allow-Origin"] = origin
        resp.headers["Access-Control-Allow-Headers"] = "Content-Type"
        resp.headers["Access-Control-Allow-Methods"] = "POST, GET, OPTIONS"
    return resp

@app.route("/api/chat", methods=["POST", "OPTIONS"])
def chat():
    if request.method == "OPTIONS":
        return "", 204
    ip = request.headers.get("CF-Connecting-IP") or request.remote_addr or "unknown"
    if rate_limited(ip):
        return jsonify({"error": "请求太频繁，请稍后再试"}), 429
    body = request.get_json(silent=True) or {}
    user_msg = (body.get("message") or "").strip()
    if not user_msg:
        return jsonify({"error": "消息不能为空"}), 400
    if len(user_msg) > 500:
        return jsonify({"error": "消息太长"}), 400
    history = body.get("history") or []
    history = history[-12:]
    knowledge = load_knowledge()
    messages = [{"role": "system", "content": SYSTEM_PROMPT.format(knowledge=knowledge)}]
    for h in history:
        if h.get("role") in ("user", "assistant") and h.get("content"):
            messages.append({"role": h["role"], "content": str(h["content"])[:500]})
    messages.append({"role": "user", "content": user_msg})
    last_err = None
    for name, fn in PROVIDERS:
        try:
            reply = fn(messages)
            return jsonify({"reply": reply.strip(), "provider": name})
        except Exception as e:
            last_err = "%s: %s" % (name, e)
            continue
    app.logger.warning("all providers failed: %s", last_err)
    return jsonify({"reply": "抱歉，AI 客服暂时开小差了，请稍后再试，或联系人工客服。"}), 503

@app.route("/api/health", methods=["GET"])
def health():
    return jsonify({
        "ok": True,
        "providers": [n for n, _ in PROVIDERS],
        "cf_configured": bool(CF_ACCOUNT_ID and CF_API_TOKEN),
        "agnes_configured": bool(AGNES_API_KEY),
    })

application = app

if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000)
