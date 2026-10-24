# shop-ai 客服网关 · 部署步骤（给他看的版本）

## 他要做的（约 10 分钟，仪表盘点点点就行）

1. **先关手机 VPN**（开着全局代理 Cloudflare 验证会转圈，之前卡过就是这个原因），
   然后电脑/手机浏览器打开 Cloudflare 仪表盘，登录 qlinghl@gmail.com。
2. 左侧 **Workers 和 Pages** → **创建** → **创建 Worker** → 起名 `shop-ai` → **部署**。
3. 进这个 Worker → **编辑代码** → 把 `worker.js` 的全部内容粘贴进去 → **保存并部署**。
4. 加 AI 绑定：Worker 页面 → **设置** → **绑定** → **添加绑定** →
   变量名填 `AI`，类型选 **Workers AI** → 保存。
   （这一步是免费第一棒"Cloudflare 模型"的钥匙，不用 Key）
5. 加 Secrets（设置 → **变量和机密** → 机密里逐个添加）：
   - `AGNES_KEY` = 你的 Agnes Key（`sk-`开头那个）
   - 后面每拿到一个 Key 就加一个：`GROQ_KEY`、`GEMINI_KEY`、`MINIMAX_KEY`、`SENNOVA_KEY`、`KIMI_KEY`
   - 每次加完点 **保存**（Worker 会自动重新部署）
6. 把 Worker 的访问地址复制下来（形如 `https://shop-ai.xxx.workers.dev`），发给我。

## 我来做的（他发我地址后）

1. 把 `chat-widget-snippet.html` 里的 `__SHOP_AI_WORKER_URL__` 换成他的 Worker 地址；
2. 把这段代码粘到三个页面源码（`~/workspace/shop-deploy/` 下的 index.html、chatgpt.html、x-premium.html）
   每个 `</body>` 之前；
3. 跑 `tools/build.py` 重新构建（混淆保护照常），部署到线上；
4. 实测：打开页面点右下角 💬，问"多少钱"，看 AI 能不能按真实价格回答。

## 他还差我的两样东西（部署前不急，上线前给我就行）

1. **客服微信号**：AI 答不上来时会推给客户。现在代码里是占位符 `WECHAT_PLACEHOLDER`，
   他给我微信号后我替换掉重新部署（30 秒的事）。
2. **第一个 Key**（Agnes 的就行）：Secret 加好后告诉我，我先验证链路通不通。

## 以后加 Key / 换顺序

- 加 Key：仪表盘 Secrets 里加一行就行，不用改代码，网关会自动启用。
- MiniMax 免费到 2026-11-07：到期前我会提醒，到时把 `MINIMAX_KEY` 这个 Secret 删掉即可。
