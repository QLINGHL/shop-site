# shop-ai 后端

AI 客服网关，跑在 AlwaysData 小主机上。

## 结构
- `app.py` — Flask 应用，`POST /api/chat`，`GET /api/health`
- `knowledge.txt` — 店铺知识库（三页面全量文字提取）
- `.env` — 密钥（600 权限，不进版本控制）
  - `AGNES_API_KEY` — Agnes API Key
  - `CF_ACCOUNT_ID` — Cloudflare Account ID
  - `CF_API_TOKEN` — Cloudflare API Token（Workers AI 读权限）
  - `AGNES_BASE` — 可选，默认 https://apihub.agnes-ai.com/v1

## 轮询顺序
1. Cloudflare Workers AI (`@cf/openai/gpt-oss-120b`)
2. Agnes AI (`agnes-3-flash`)
3. 加新渠道：在 `PROVIDERS` 列表加一行

## 部署（AlwaysData）
```bash
# 传文件
scp -i ~/.ssh/id_ed25519 -r shop-api qlinghl@ssh-qlinghl.alwaysdata.net:~/www/
# SSH 上去装依赖、起服务（或配 AlwaysData 的 Python WSGI）
```

## 本地测试
```bash
cd shop-api && python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt
python app.py
curl -X POST localhost:5000/api/chat -H 'Content-Type: application/json' \
  -d '{"message":"多少钱？"}'
```
