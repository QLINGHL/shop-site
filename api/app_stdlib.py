#!/usr/bin/env python3
"""shop-ai 后端：AI 客服网关（纯标准库，无第三方依赖）"""
import os
import time
import json
import random
import hmac
import hashlib
import urllib.request
import urllib.error
import urllib.parse
import ipaddress
import threading
import queue
from collections import defaultdict
from wsgiref.util import setup_testing_defaults

def _load_dotenv():
    p = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")
    try:
        with open(p, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, v = line.split("=", 1)
                    os.environ.setdefault(k.strip(), v.strip())
    except FileNotFoundError:
        pass

_load_dotenv()

CF_ACCOUNT_ID = os.environ.get("CF_ACCOUNT_ID", "")
CF_API_TOKEN = os.environ.get("CF_API_TOKEN", "")
AGNES_API_KEY = os.environ.get("AGNES_API_KEY", "")
AGNES_API_KEYS = [k.strip() for k in os.environ.get("AGNES_API_KEYS", "").split(",") if k.strip()]
if not AGNES_API_KEYS and AGNES_API_KEY:
    AGNES_API_KEYS = [AGNES_API_KEY]
AGNES_BASE = os.environ.get("AGNES_BASE", "https://apihub.agnes-ai.com/v1")
SENSENOVA_API_KEY = os.environ.get("SENSENOVA_API_KEY", "")
SENSENOVA_BASE = os.environ.get("SENSENOVA_BASE", "https://token.sensenova.cn/v1")
SENSENOVA_MODEL = os.environ.get("SENSENOVA_MODEL", "sensenova-6.8-flash-lite")
# key 轮询状态：记录每个 key 被限流的冷却到期时间
_key_cooldown = {}
_key_index = [0]

def _all_endpoints():
    """返回所有可用端点：(名字, base, key, model) 列表。"""
    eps = []
    for idx, k in enumerate(AGNES_API_KEYS):
        eps.append(("agnes%d" % idx, AGNES_BASE, k, AGNES_MODEL))
    if SENSENOVA_API_KEY:
        eps.append(("sensenova", SENSENOVA_BASE, SENSENOVA_API_KEY, SENSENOVA_MODEL))
    return eps

def _pick_key():
    """轮询取一个未被限流的 key；全被限流则取冷却最早到期的。"""
    now = time.time()
    n = len(AGNES_API_KEYS)
    for _ in range(n):
        i = _key_index[0] % n
        _key_index[0] += 1
        if _key_cooldown.get(i, 0) <= now:
            return i, AGNES_API_KEYS[i]
    i = min(range(n), key=lambda x: _key_cooldown.get(x, 0))
    return i, AGNES_API_KEYS[i]

def _cool_key(i, seconds=60):
    _key_cooldown[i] = time.time() + seconds
SHOP_SECRET = os.environ.get("SHOP_SECRET", "")
CF_MODEL = "@cf/openai/gpt-oss-120b"
AGNES_MODEL = "agnes-3.0-flash"
ALLOWED_ORIGINS = {
    "https://shop.qlinghl.workers.dev",
    "https://qlinghl.alwaysdata.net",
}

def load_knowledge():
    p = os.path.join(os.path.dirname(os.path.abspath(__file__)), "knowledge.txt")
    try:
        with open(p, encoding="utf-8") as f:
            return f.read()
    except FileNotFoundError:
        return ""


# Cloudflare 官方出口 IP 段（https://www.cloudflare.com/ips）
# 仅允许经 Cloudflare 代理的请求直达后端，隐藏真实服务器地址
CF_NETWORKS = [
    "173.245.48.0/20", "103.21.244.0/22", "103.22.200.0/22", "103.31.4.0/22",
    "141.101.64.0/18", "108.162.192.0/18", "190.93.240.0/20", "188.114.96.0/20",
    "197.234.240.0/22", "198.41.128.0/17", "162.158.0.0/15", "104.16.0.0/13",
    "104.24.0.0/14", "172.64.0.0/13", "131.0.72.0/22",
    "2400:cb00::/32", "2606:4700::/32", "2803:f800::/32", "2405:b500::/32",
    "2405:8100::/32", "2a06:98c0::/29", "2c0f:f248::/32",
]
_CF_NETS = [ipaddress.ip_network(c) for c in CF_NETWORKS]

def _is_cloudflare_ip(ip):
    try:
        addr = ipaddress.ip_address(ip)
        return any(addr in n for n in _CF_NETS)
    except ValueError:
        return False

SYSTEM_PROMPT = """你是这家数码商品小店的 AI 客服助手。

【店铺知识库】
{knowledge}

【规则】只能按知识库回答，不知道就说"这个问题我暂时答不上来"，绝不编造。用简洁中文，不超过100字。"""

_hits = defaultdict(list)

def rate_limited(ip, limit=10, window=60):
    now = time.time()
    lst = _hits[ip]
    lst[:] = [t for t in lst if now - t < window]
    if len(lst) >= limit:
        return True
    lst.append(now)
    return False

def _post_json(url, payload, headers, timeout=30):
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers=headers, method="POST")
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8"))

def agnes_chat(messages):
    if not AGNES_API_KEYS:
        raise RuntimeError("Agnes key not configured")
    last_err = None
    for _ in range(len(AGNES_API_KEYS)):
        i, key = _pick_key()
        try:
            data = _post_json(
                AGNES_BASE + "/chat/completions",
                {"model": AGNES_MODEL, "messages": messages, "max_tokens": 300, "temperature": 0.7},
                {"Authorization": "Bearer " + key, "Content-Type": "application/json"})
            return data["choices"][0]["message"]["content"]
        except urllib.error.HTTPError as e:
            last_err = e
            if e.code == 429:
                _cool_key(i)
                continue
            raise
    raise last_err or RuntimeError("all agnes keys rate-limited")

def agnes_chat_stream(messages):
    """流式调用 Agnes，yield 每个 content delta。key 轮询，429 自动换下一个。"""
    if not AGNES_API_KEYS:
        raise RuntimeError("Agnes key not configured")
    last_err = None
    for _ in range(len(AGNES_API_KEYS)):
        i, key = _pick_key()
        try:
            for delta in _stream_one_key(messages, key):
                yield delta
            return
        except urllib.error.HTTPError as e:
            last_err = e
            if e.code == 429:
                _cool_key(i)
                continue
            raise
    raise last_err or RuntimeError("all agnes keys rate-limited")

def _stream_one_endpoint(messages, base, key, model):
    """用单个端点做流式请求，yield delta。OpenAI 兼容。"""
    payload = {"model": model, "messages": messages, "max_tokens": 300,
               "temperature": 0.7, "stream": True}
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        base + "/chat/completions", data=data,
        headers={"Authorization": "Bearer " + key,
                 "Content-Type": "application/json"}, method="POST")
    with urllib.request.urlopen(req, timeout=60) as r:
        buf = b""
        while True:
            chunk = r.read(1024)
            if not chunk:
                break
            buf += chunk
            while b"\n" in buf:
                line, buf = buf.split(b"\n", 1)
                line = line.strip()
                if not line.startswith(b"data:"):
                    continue
                payload_str = line[5:].strip().decode("utf-8", "ignore")
                if payload_str == "[DONE]":
                    return
                try:
                    obj = json.loads(payload_str)
                    delta = obj["choices"][0]["delta"].get("content", "")
                    if delta:
                        yield delta
                except (ValueError, KeyError, IndexError):
                    continue

def stream_random_pick(messages):
    """4 端点随机排序挨个试：3 Agnes key + 1 商汤。失败自动换下一个。"""
    import random
    eps = _all_endpoints()
    if not eps:
        raise RuntimeError("no endpoints configured")
    order = list(range(len(eps)))
    random.shuffle(order)
    last_err = None
    for idx in order:
        name, base, key, model = eps[idx]
        # 跳过冷却中的 Agnes key
        if name.startswith("agnes"):
            agnes_idx = int(name[5:])
            if _key_cooldown.get(agnes_idx, 0) > time.time():
                continue
        try:
            got_any = False
            for delta in _stream_one_endpoint(messages, base, key, model):
                got_any = True
                yield delta
            if got_any:
                print("stream ok via %s" % name, flush=True)
                return
            # 连上了但一个字没出：算失败，换下一个
            last_err = RuntimeError("%s empty response" % name)
        except urllib.error.HTTPError as e:
            last_err = e
            print("stream %s HTTP %s, trying next" % (name, e.code), flush=True)
            if e.code == 429 and name.startswith("agnes"):
                _cool_key(int(name[5:]))
            continue
        except Exception as e:
            last_err = e
            print("stream %s error %s, trying next" % (name, e), flush=True)
            continue
    raise last_err or RuntimeError("all endpoints failed")

def _stream_one_key(messages, key):
    """用单个 key 做流式请求，yield delta。"""
    payload = {"model": AGNES_MODEL, "messages": messages, "max_tokens": 300,
               "temperature": 0.7, "stream": True}
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        AGNES_BASE + "/chat/completions", data=data,
        headers={"Authorization": "Bearer " + key,
                 "Content-Type": "application/json"}, method="POST")
    with urllib.request.urlopen(req, timeout=60) as r:
        buf = b""
        while True:
            chunk = r.read(1024)
            if not chunk:
                break
            buf += chunk
            while b"\n" in buf:
                line, buf = buf.split(b"\n", 1)
                line = line.strip()
                if not line.startswith(b"data:"):
                    continue
                payload_str = line[5:].strip().decode("utf-8", "ignore")
                if payload_str == "[DONE]":
                    return
                try:
                    obj = json.loads(payload_str)
                    delta = obj["choices"][0]["delta"].get("content", "")
                    if delta:
                        yield delta
                except (ValueError, KeyError, IndexError):
                    continue

def agnes_chat_stream_hedged(messages, timeout_first=8):
    """三 key 同时发，谁先出首字用谁，其余丢弃。解决单个 key 首字慢的问题。"""
    if not AGNES_API_KEYS:
        raise RuntimeError("Agnes key not configured")
    n = len(AGNES_API_KEYS)
    if n == 1:
        for delta in agnes_chat_stream(messages):
            yield delta
        return
    result_q = queue.Queue()
    stop = threading.Event()

    def worker(idx, key):
        try:
            gen = _stream_one_key(messages, key)
            first = next(gen, None)
            if first is None:
                result_q.put((idx, "empty", None))
                return
            # 抢到首字：把自己注册为 winner
            result_q.put((idx, "win", (first, gen)))
        except urllib.error.HTTPError as e:
            if e.code == 429:
                _cool_key(idx)
            result_q.put((idx, "error", e))
        except Exception as e:
            result_q.put((idx, "error", e))

    threads = []
    for idx, key in enumerate(AGNES_API_KEYS):
        # 跳过冷却中的 key
        if _key_cooldown.get(idx, 0) > time.time():
            continue
        t = threading.Thread(target=worker, args=(idx, key), daemon=True)
        t.start()
        threads.append(t)
    if not threads:
        # 全在冷却中：降级为普通轮询
        for delta in agnes_chat_stream(messages):
            yield delta
        return

    winner_gen = None
    errors = []
    deadline = time.time() + timeout_first
    try:
        while time.time() < deadline:
            try:
                idx, kind, payload = result_q.get(timeout=max(0.1, deadline - time.time()))
            except queue.Empty:
                continue
            if kind == "win":
                first, gen = payload
                winner_gen = gen
                yield first
                break
            elif kind == "error":
                errors.append(payload)
        if winner_gen is None:
            # 超时都没出字：用第一个有响应的，或抛错
            raise RuntimeError("agnes hedged timeout: %s" % (errors[0] if errors else "no response"))
        for delta in winner_gen:
            if stop.is_set():
                break
            yield delta
    finally:
        stop.set()

def cf_chat(messages):
    if not (CF_ACCOUNT_ID and CF_API_TOKEN):
        raise RuntimeError("CF credentials not configured")
    url = "https://api.cloudflare.com/client/v4/accounts/%s/ai/run/%s" % (CF_ACCOUNT_ID, CF_MODEL)
    data = _post_json(
        url, {"messages": messages, "max_tokens": 300},
        {"Authorization": "Bearer " + CF_API_TOKEN, "Content-Type": "application/json"})
    if not data.get("success"):
        raise RuntimeError("CF AI error: %s" % data.get("errors"))
    res = data["result"]
    if isinstance(res, dict) and "response" in res:
        return res["response"]
    return res["choices"][0]["message"]["content"]

PROVIDERS = [("agnes", agnes_chat), ("cloudflare", cf_chat)]

def _resp(start_response, status, obj, origin=""):
    body = json.dumps(obj, ensure_ascii=False).encode("utf-8")
    h = [("Content-Type", "application/json; charset=utf-8"), ("Content-Length", str(len(body)))]
    if origin in ALLOWED_ORIGINS:
        h += [("Access-Control-Allow-Origin", origin),
              ("Access-Control-Allow-Headers", "Content-Type"),
              ("Access-Control-Allow-Methods", "POST, GET, OPTIONS")]
    start_response(status, h)
    return [body]

# ================= 16688 采购（开放平台 API） =================
# 文档：https://www.16688.com.cn/api/purchase/docs/
# 网关 https://www.16688.com.cn/openApi ；认证 app_id + secret，HMAC-SHA256
# （2026-10-12 真机验证：签名算法与 merchant/balance 路径调通）
# 凭证与管理密钥全部走服务端 .env，绝不进代码：
#   K16688_APP_ID / K16688_APP_SECRET（开放平台「接入凭证」区获取）
#   PROCURE_ADMIN_KEY（自行设定 32 位以上随机串，调用时放 X-Admin-Key 头）
K16688_APP_ID = os.environ.get("K16688_APP_ID", "")
K16688_APP_SECRET = os.environ.get("K16688_APP_SECRET", "")
K16688_GATEWAY = os.environ.get("K16688_GATEWAY", "https://www.16688.com.cn/openApi").rstrip("/")
PROCURE_ADMIN_KEY = os.environ.get("PROCURE_ADMIN_KEY", "")

# 可售 SKU 白名单（我方 sku -> 16688 商品）。
# 下单必须用上游供应商的货源商品编号 upstream_goods_no（向供应商拿货），
# 不是自己店铺的 goods_id。2026-10-12 真机验证。
K16688_SKUS = {
    "chatgpt-plus": {"goods_id": "G19939874", "upstream_goods_no": "G29754567",
                     "name": "Plus CDK 菲区115", "cost": 109.0,
                     "fallback_price": 114.45},
}

# 公开卖价规则：售价 = 上游实时成本 × PRICE_MARKUP（默认 1.05，即加价 5%）。
# 成本变动时卖价自动跟随，保证不亏本卖；上游接口异常时用 fallback_price。
PRICE_MARKUP = 1.05
PRICE_CACHE_TTL = 600  # 上游价格缓存 10 分钟
_price_cache = {"at": 0.0, "data": None}
_sku_limits = {}  # sku -> 上游单次限购数（goods/detail 的 limit_quantity）
K16688_MAX_QTY = 10


class _KProcureError(Exception):
    pass


def _k_norm_value(v):
    if isinstance(v, bool):
        return "true" if v else "false"
    if v is None:
        return ""
    if isinstance(v, dict):
        return json.dumps({k: _k_norm_json(v[k]) for k in sorted(v.keys())},
                          ensure_ascii=False, separators=(",", ":"))
    if isinstance(v, (list, tuple)):
        return json.dumps([_k_norm_json(x) for x in v],
                          ensure_ascii=False, separators=(",", ":"))
    return str(v)


def _k_norm_json(v):
    if isinstance(v, bool):
        return v
    if isinstance(v, dict):
        return {k: _k_norm_json(v[k]) for k in sorted(v.keys())}
    if isinstance(v, (list, tuple)):
        return [_k_norm_json(x) for x in v]
    return v


def _k_sign(controller, action, params):
    items = sorted((k, v) for k, v in params.items() if k != "sign")
    param_str = "&".join("%s=%s" % (k, _k_norm_value(v)) for k, v in items)
    raw = "\n".join(["POST", controller.lower(), action.lower(), param_str])
    return hmac.new(K16688_APP_SECRET.encode("utf-8"),
                    raw.encode("utf-8"), hashlib.sha256).hexdigest()


def _k_call(path, params):
    """调 16688 接口。path 如 'merchant/balance'。成功返回 data，失败抛 _KProcureError。"""
    if not (K16688_APP_ID and K16688_APP_SECRET):
        raise _KProcureError("服务端未配置 K16688_APP_ID / K16688_APP_SECRET")
    controller, action = path.split("/", 1)
    body = dict(params or {})
    body["app_id"] = K16688_APP_ID
    body["timestamp"] = int(time.time())
    body["nonce"] = "%032x" % random.getrandbits(128)
    body["sign"] = _k_sign(controller, action, body)
    try:
        payload = _post_json(K16688_GATEWAY + "/" + path, body,
                             {"Content-Type": "application/json"}, timeout=25)
    except urllib.error.HTTPError as e:
        raise _KProcureError("上游 HTTP %s" % e.code)
    except Exception as e:
        raise _KProcureError("上游请求失败：%s" % e)
    if not isinstance(payload, dict) or payload.get("code") != 1:
        msg = payload.get("msg", "未知错误") if isinstance(payload, dict) else "非 JSON 响应"
        raise _KProcureError("上游返回失败：%s" % msg)
    return payload.get("data")


def _k_extract_cards(data):
    if isinstance(data, dict):
        for key in ("cards", "card_list", "list", "data"):
            if key in data:
                return _k_extract_cards(data[key])
        no = data.get("card_no") or data.get("cardNo") or data.get("kami") or ""
        pwd = data.get("card_pwd") or data.get("cardPwd") or data.get("password") or ""
        return [(str(no), str(pwd))] if no else []
    if isinstance(data, (list, tuple)):
        out = []
        for item in data:
            out.extend(_k_extract_cards(item))
        return out
    if isinstance(data, str) and data.strip():
        return [(data.strip(), "")]
    return []


def _procure_authed(environ):
    """双 gate：Cloudflare 出口 IP（或 SHOP_SECRET）+ 管理密钥。未配置管理密钥时一律拒绝。"""
    if not PROCURE_ADMIN_KEY:
        return False
    peer = environ.get("REMOTE_ADDR", "")
    ok_ip = _is_cloudflare_ip(peer)
    ok_key = SHOP_SECRET and environ.get("HTTP_X_SHOP_SECRET") == SHOP_SECRET
    if not (ok_ip or ok_key):
        return False
    return environ.get("HTTP_X_ADMIN_KEY", "") == PROCURE_ADMIN_KEY


def _handle_prices(start_response, origin):
    """GET /api/prices — 公开接口，无需鉴权。
    返回各 SKU 的实时卖价（上游成本 × 加价倍数）与库存。
    只暴露卖价/库存，不暴露成本价与任何密钥。10 分钟缓存。"""
    now = time.time()
    if _price_cache["data"] and now - _price_cache["at"] < PRICE_CACHE_TTL:
        return _resp(start_response, "200 OK", _price_cache["data"], origin)
    items = []
    for sku, info in K16688_SKUS.items():
        price, stock = info.get("fallback_price", 0), 0
        try:
            d = _k_call("goods/detail", {"goods_no": info["upstream_goods_no"]})
            cost = float(d.get("unit_price") or 0)
            stock = int(d.get("available_quantity") or 0)
            _sku_limits[sku] = int(d.get("limit_quantity") or K16688_MAX_QTY)
            if cost > 0:
                price = round(cost * PRICE_MARKUP, 2)
        except _KProcureError:
            pass  # 上游异常：用 fallback 价格，库存记 0
        items.append({"sku": sku, "name": info["name"], "price": price,
                      "in_stock": stock > 0, "stock": stock})
    data = {"prices": items, "updated_at": int(now)}
    _price_cache["at"] = now
    _price_cache["data"] = data
    return _resp(start_response, "200 OK", data, origin)


def _handle_procure(environ, start_response, origin, path, method, body):
    ip = (environ.get("HTTP_X_REAL_IP")
          or environ.get("HTTP_CF_CONNECTING_IP")
          or environ.get("REMOTE_ADDR", "?"))
    if not _procure_authed(environ):
        return _resp(start_response, "403 Forbidden", {"error": "forbidden"}, origin)
    if rate_limited(ip):
        return _resp(start_response, "429 Too Many Requests", {"error": "too fast"}, origin)
    if path == "/api/procure/skus" and method == "GET":
        skus = [{"sku": s, "name": v["name"], "cost": v["cost"]}
                for s, v in K16688_SKUS.items()]
        return _resp(start_response, "200 OK", {"skus": skus}, origin)
    if path == "/api/procure/balance" and method == "GET":
        try:
            data = _k_call("merchant/balance", {})
        except _KProcureError as e:
            return _resp(start_response, "502 Bad Gateway", {"error": str(e)}, origin)
        return _resp(start_response, "200 OK", {"balance": data}, origin)
    if path == "/api/procure" and method == "POST":
        sku = str(body.get("sku", "")).strip()
        if sku not in K16688_SKUS:
            return _resp(start_response, "400 Bad Request", {"error": "unknown sku"}, origin)
        try:
            qty = int(body.get("quantity", 1))
        except (TypeError, ValueError):
            qty = 0
        # 上游单次限购（本进程未知时实时查一次，保证多进程下也正确）
        sku_max = _sku_limits.get(sku)
        if sku_max is None:
            try:
                _d = _k_call("goods/detail", {"goods_no": K16688_SKUS[sku]["upstream_goods_no"]})
                sku_max = int(_d.get("limit_quantity") or K16688_MAX_QTY)
            except _KProcureError:
                sku_max = K16688_MAX_QTY
            _sku_limits[sku] = sku_max
        sku_max = min(K16688_MAX_QTY, sku_max)
        if not 1 <= qty <= sku_max:
            return _resp(start_response, "400 Bad Request",
                         {"error": "该商品每次限购 %d 件" % sku_max}, origin)
        # 幂等：调用方没传订单号时自动生成并返回，重试不会重复扣款
        buyer_no = str(body.get("buyer_order_no", "")).strip()[:64]
        out_trade_no = buyer_no or ("M%d%06d" % (int(time.time()), random.randint(0, 999999)))
        # 下单用上游供应商的货源商品编号（upstream_goods_no），不是自家店铺编号
        params = {"goods_no": K16688_SKUS[sku]["upstream_goods_no"],
                  "quantity": qty, "out_trade_no": out_trade_no}
        try:
            order = _k_call("purchase/create", params)
        except _KProcureError as e:
            msg = str(e)
            if "余额" in msg or "balance" in msg.lower():
                return _resp(start_response, "402 Payment Required",
                             {"error": "运营钱包余额不足，请先充值", "detail": msg}, origin)
            return _resp(start_response, "502 Bad Gateway", {"error": msg}, origin)
        order_no = ""
        if isinstance(order, dict):
            order_no = str(order.get("order_no") or order.get("orderNo")
                            or order.get("id") or "")
        cards = []
        last_err = ""
        for _ in range(3):
            try:
                detail = _k_call("purchase/query", {"order_no": order_no}) if order_no else {}
                cards = _k_extract_cards(detail)
                if cards:
                    break
            except _KProcureError as e:
                last_err = str(e)
            time.sleep(2)
        if not cards:
            print("procure pending cards, order=%s err=%s" % (order_no, last_err), flush=True)
            return _resp(start_response, "200 OK",
                         {"ok": True, "pending": True, "order_no": order_no, "sku": sku,
                          "out_trade_no": out_trade_no,
                          "note": "下单成功，卡密尚未返回，请用订单号重查 /api/procure/cards"}, origin)
        card_list = [{"card_no": c[0], "card_pwd": c[1]} for c in cards]
        return _resp(start_response, "200 OK",
                     {"ok": True, "sku": sku, "quantity": qty, "order_no": order_no,
                      "out_trade_no": out_trade_no, "cards": card_list,
                      "card_no": card_list[0]["card_no"],
                      "card_pwd": card_list[0]["card_pwd"]}, origin)
    if path == "/api/procure/cards" and method in ("GET", "POST"):
        # 按上游订单号重查卡密（下单返回 pending 时用，避免重复下单扣款）。
        # 注意：代理层会丢掉 query string，所以 POST body 传 order_no 最稳。
        order_no = str(body.get("order_no", "") or "")[:64]
        if not order_no:
            qs = environ.get("QUERY_STRING", "")
            for kv in qs.split("&"):
                if kv.startswith("order_no="):
                    order_no = urllib.parse.unquote(kv[len("order_no="):])[:64]
        if not order_no:
            return _resp(start_response, "400 Bad Request",
                         {"error": "缺少 order_no 参数"}, origin)
        try:
            detail = _k_call("purchase/query", {"order_no": order_no})
            cards = _k_extract_cards(detail)
        except _KProcureError as e:
            return _resp(start_response, "502 Bad Gateway", {"error": str(e)}, origin)
        if not cards:
            return _resp(start_response, "200 OK",
                         {"ok": True, "pending": True, "order_no": order_no,
                          "note": "卡密尚未返回，稍后重查"}, origin)
        card_list = [{"card_no": c[0], "card_pwd": c[1]} for c in cards]
        return _resp(start_response, "200 OK",
                     {"ok": True, "order_no": order_no, "cards": card_list}, origin)
    return _resp(start_response, "404 Not Found", {"error": "not found"}, origin)
# ================= 16688 采购结束 =================

def application(environ, start_response):
    setup_testing_defaults(environ)
    method = environ.get("REQUEST_METHOD", "GET")
    path = environ.get("PATH_INFO", "/")
    origin = environ.get("HTTP_ORIGIN", "")
    if method == "OPTIONS":
        start_response("204 No Content", [
            ("Access-Control-Allow-Origin", origin if origin in ALLOWED_ORIGINS else ""),
            ("Access-Control-Allow-Headers", "Content-Type"),
            ("Access-Control-Allow-Methods", "POST, GET, OPTIONS"),
            ("Content-Length", "0")])
        return [b""]
    if path == "/api/health":
        return _resp(start_response, "200 OK", {"ok": True}, origin)
    if path == "/api/chat" and method == "POST":
        # 仅允许经 Cloudflare 来的请求（代理 Worker 出口 IP），防后端地址暴露后被直接攻击；
        # 备用：携带正确密钥的请求也放行（便于直接调试）
        peer = environ.get("REMOTE_ADDR", "")
        ok_ip = _is_cloudflare_ip(peer)
        ok_key = SHOP_SECRET and environ.get("HTTP_X_SHOP_SECRET") == SHOP_SECRET
        if not (ok_ip or ok_key):
            return _resp(start_response, "403 Forbidden", {"error": "forbidden"}, origin)
        ip = (environ.get("HTTP_X_REAL_IP")
              or environ.get("HTTP_CF_CONNECTING_IP")
              or environ.get("REMOTE_ADDR", "?"))
        if rate_limited(ip):
            return _resp(start_response, "429 Too Many Requests",
                         {"error": "too fast", "reply": "你问得太快了，休息 1 分钟再问我吧。"}, origin)
        try:
            length = int(environ.get("CONTENT_LENGTH", 0) or 0)
        except ValueError:
            length = 0
        raw = environ["wsgi.input"].read(length) if length > 0 else b""
        try:
            body = json.loads(raw.decode("utf-8")) if raw else {}
        except ValueError:
            body = {}
        msg = (body.get("message") or "").strip()
        if not msg:
            return _resp(start_response, "400 Bad Request", {"error": "empty"}, origin)
        if len(msg) > 2000:
            msg = msg[:2000]
        hist = (body.get("history") or [])[-12:]
        knowledge = load_knowledge()
        messages = [{"role": "system", "content": SYSTEM_PROMPT.format(knowledge=knowledge)}]
        for hh in hist:
            if hh.get("role") in ("user", "assistant") and hh.get("content"):
                messages.append({"role": hh["role"], "content": str(hh["content"])[:500]})
        messages.append({"role": "user", "content": msg})
        # 4 端点随机排序挨个试：3 Agnes + 1 商汤
        import random
        eps = _all_endpoints()
        order = list(range(len(eps)))
        random.shuffle(order)
        last_err = None
        for idx in order:
            ep_name, ep_base, ep_key, ep_model = eps[idx]
            if ep_name.startswith("agnes"):
                agnes_idx = int(ep_name[5:])
                if _key_cooldown.get(agnes_idx, 0) > time.time():
                    continue
            try:
                data = _post_json(
                    ep_base + "/chat/completions",
                    {"model": ep_model, "messages": messages, "max_tokens": 300, "temperature": 0.7},
                    {"Authorization": "Bearer " + ep_key, "Content-Type": "application/json"})
                reply = data["choices"][0]["message"]["content"]
                return _resp(start_response, "200 OK", {"reply": reply, "provider": ep_name}, origin)
            except urllib.error.HTTPError as e:
                last_err = "%s: HTTP %s" % (ep_name, e.code)
                if e.code == 429 and ep_name.startswith("agnes"):
                    _cool_key(int(ep_name[5:]))
                continue
            except Exception as e:
                last_err = "%s: %s" % (ep_name, e)
                continue
        # detail 只写日志，不返回给客户端（防内部信息泄露）
        print("chat providers failed: %s" % last_err, flush=True)
        return _resp(start_response, "503 Service Unavailable",
                     {"reply": "抱歉，AI 客服暂时开小差了，请稍后再试。"}, origin)
    if path == "/api/chat/stream" and method == "POST":
        peer = environ.get("REMOTE_ADDR", "")
        ok_ip = _is_cloudflare_ip(peer)
        ok_key = SHOP_SECRET and environ.get("HTTP_X_SHOP_SECRET") == SHOP_SECRET
        if not (ok_ip or ok_key):
            return _resp(start_response, "403 Forbidden", {"error": "forbidden"}, origin)
        ip = (environ.get("HTTP_X_REAL_IP")
              or environ.get("HTTP_CF_CONNECTING_IP")
              or environ.get("REMOTE_ADDR", "?"))
        if rate_limited(ip):
            return _resp(start_response, "429 Too Many Requests",
                         {"error": "too fast", "reply": "你问得太快了，休息 1 分钟再问我吧。"}, origin)
        try:
            length = int(environ.get("CONTENT_LENGTH", 0) or 0)
        except ValueError:
            length = 0
        raw = environ["wsgi.input"].read(length) if length > 0 else b""
        try:
            body = json.loads(raw.decode("utf-8")) if raw else {}
        except ValueError:
            body = {}
        msg = (body.get("message") or "").strip()
        if not msg:
            return _resp(start_response, "400 Bad Request", {"error": "empty"}, origin)
        if len(msg) > 2000:
            msg = msg[:2000]
        hist = (body.get("history") or [])[-12:]
        knowledge = load_knowledge()
        messages = [{"role": "system", "content": SYSTEM_PROMPT.format(knowledge=knowledge)}]
        for hh in hist:
            if hh.get("role") in ("user", "assistant") and hh.get("content"):
                messages.append({"role": hh["role"], "content": str(hh["content"])[:500]})
        messages.append({"role": "user", "content": msg})
        # SSE 响应头
        h = [("Content-Type", "text/event-stream; charset=utf-8"),
             ("Cache-Control", "no-cache"),
             ("X-Accel-Buffering", "no")]
        if origin in ALLOWED_ORIGINS:
            h += [("Access-Control-Allow-Origin", origin)]
        start_response("200 OK", h)
        def gen():
            try:
                for delta in stream_random_pick(messages):
                    yield ("data: " + json.dumps({"delta": delta}, ensure_ascii=False) + "\n\n").encode("utf-8")
            except Exception as e:
                print("stream failed, fallback: %s" % e, flush=True)
                # 流式失败则降级为一次性返回
                try:
                    reply = agnes_chat(messages)
                    yield ("data: " + json.dumps({"delta": reply}, ensure_ascii=False) + "\n\n").encode("utf-8")
                except Exception as e2:
                    yield ("data: " + json.dumps({"error": "抱歉，AI 客服暂时开小差了，请稍后再试。"}, ensure_ascii=False) + "\n\n").encode("utf-8")
            yield b"data: [DONE]\n\n"
        return gen()
    if path == "/api/prices" and method == "GET":
        ip = (environ.get("HTTP_X_REAL_IP")
              or environ.get("HTTP_CF_CONNECTING_IP")
              or environ.get("REMOTE_ADDR", "?"))
        if rate_limited(ip):
            return _resp(start_response, "429 Too Many Requests", {"error": "too fast"}, origin)
        return _handle_prices(start_response, origin)
    if path.startswith("/api/procure"):
        try:
            length = int(environ.get("CONTENT_LENGTH", 0) or 0)
        except ValueError:
            length = 0
        raw = environ["wsgi.input"].read(length) if length > 0 else b""
        try:
            pbody = json.loads(raw.decode("utf-8")) if raw else {}
        except ValueError:
            pbody = {}
        return _handle_procure(environ, start_response, origin, path, method, pbody)
    return _resp(start_response, "404 Not Found", {"error": "not found"}, origin)

if __name__ == "__main__":
    from wsgiref.simple_server import make_server
    port = int(os.environ.get("PORT", "5000"))
    print("serving on :%d" % port, flush=True)
    make_server("127.0.0.1", port, application).serve_forever()
