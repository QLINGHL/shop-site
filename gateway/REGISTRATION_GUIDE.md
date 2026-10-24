# AI 客服 Key 注册攻略（大白话版）

目标：给客服网关攒免费模型的钥匙（API Key）。**先拿下第 1 批 4 个就能跑**，后面的有空再加。

⚠️ 安全：Key 别发聊天里，走 Secure Vault 给我。Key 只显示一次，复制完立刻存好。

---

## 第 1 批：今天拿下（约 20 分钟，4 个全到手就能上线）

### 1. Agnes（国内站，最省事，永久免费）
- 打开 https://agnes-ai.cn ，邮箱注册个账号
- 登录后进 API 平台 / 开发者控制台 →「API Keys」→ 创建密钥
- Key 长得像 `sk-xxxx`，只显示一次，立刻复制
- 免费额度：flash 系列模型（agnes-2.5-flash）官方价目表 $0/1M tokens，不限期免费；免费档每分钟最多 20 次
- 拿到的 Key 对应的接口地址：`https://apihub.agnes-ai.cn/v1`（代码里已默认填好）

### 2. Cloudflare Workers AI（不用 Key，他已有账号）
- 你已经有 Cloudflare 账号了（qlinghl@gmail.com），这个不用注册
- 每天 1 万 neurons 免费，不用绑卡；超了只会报错不会扣钱，网关会自动切下一家
- ⚠️ 你之前注册时遇到验证无限转圈：那是因为手机 VPN 开着全局代理。**进 Cloudflare 仪表盘前先把 VPN 关了**，再打开就正常了

### 3. Google Gemini（每天 1500 次免费）
- 打开 aistudio.google.com，Google 账号登录 → 点「Get API Key」建一个
- 免费额度：Flash 模型每天约 1500 次（确切数字以页面为准）
- ⚠️ 注册页可能打不开：开 VPN 再打开，拿到 Key 就行（Key 拿到后 VPN 开关无所谓，调用是服务器端走的）

### 4. Groq（速度最快，注册拿 Key 就行）
- 打开 console.groq.com 注册 → 左侧「API Keys」→ Create API Key
- 免费额度约：每分钟 30 次、每天 1000 次（以页面为准）
- ⚠️ 注册页可能要开 VPN 才能打开；**别跟第 2 步同时搞**（开着 VPN 去 Cloudflare 会转圈）

---

## 第 2 批：有空再加（额度更大，锦上添花）

5. **MiniMax**：https://platform.minimax.io 注册 → API 页面拿 Key。模型 MiniMax-M2，**免费试用到 2026-11-07**，之后收费，到期前我会提醒你把它从链里拿掉。
6. **豆包（火山引擎）**：火山引擎控制台开 ModelArk，每月 200 万 tokens 免费（以控制台为准）；可能要实名认证。
7. **商汤**：https://token.sensenova.cn 注册，6 万积分 / 5 小时（滚动恢复）；模型 sensenova-6.8-flash-lite，接口跟 OpenAI 一样。
8. **Kimi**：platform.moonshot.cn 注册拿 Key；**硅基流动**：cloud.siliconflow.cn（要支付宝实名一下）。

---

## 顺序建议

Agnes → Cloudflare（关 VPN 进仪表盘）→ 开 VPN 拿 Gemini + Groq → 关 VPN → 第 2 批随缘。

**每拿到一个 Key 就走 Secure Vault 给我一个**，不用攒齐：Agnes 的 Key 一到，我先把整条链跑通给你看，后面的 Key 加进来就是改个配置的事。
