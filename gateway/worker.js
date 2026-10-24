/**
 * shop-ai — AI 客服网关（Cloudflare Worker）
 *
 * 链路：前端聊天框 -> POST /api/chat -> 按顺序试各家免费模型，
 * 某家额度用完 / 报错 / 限流 -> 自动换下一家，用户无感。
 *
 * 部署见 DEPLOY.md。密钥全部放 Worker 的 Secrets 里，前端永远看不到。
 */

// ---------- 知识库：只写他页面上真实有的内容，不编 ----------
// 人工客服微信：他还没给，先占位，拿到后替换 WECHAT_PLACEHOLDER
const SHOP_KNOWLEDGE = `
你是"为你精选 · 数码商品"小店的在线客服，只用中文大白话回答，尽量简短（3句话内能说完就别多说）。

【在售商品与价格】
- ChatGPT Plus/Pro：Plus ¥110/月，Pro 100 ¥640/月，Pro 200 ¥1000/月；官方充值、自助卡密兑换，自动发卡。
- Gemini Pro 18个月：¥6；官方活动，直充到自己的账号。
- X Premium：3个月 ¥23（约¥7.67/月），6个月 ¥43（约¥7.17/月）；X 官方礼物赠送到你的 X 账号开通蓝V，不需要提供密码，自动到账。
- Muse 成品号：¥6 起；邀请码助力，最高300亿词元。

【X Premium 发货与售后】
- 付款后一般几分钟内自动到账；5分钟没到=进入人工排单，站长手动处理要 5～18 小时，无需重复下单。急单不接。
- 开通前后不要修改资料（头像、昵称、简介）：刚改过资料的账号会被 X 判定为暂时无法接收赠送，只能等资料稳定后用同一张卡密重新兑换；蓝V开通后短期内改资料会重新触发 X 审核，审核不通过蓝V会被收回；因此导致的送不上或蓝V消失不在售后范围内。
- 接收账号要求：仅适用于当前没有蓝V的账号（已有蓝V无法续期）；账号最近3天内未修改过资料；官方/机构认证账号、私密账号、资料页隐藏了订阅的账号无法接收。
- 虚拟商品发货后不支持无理由退款。

【购买流程】在商品页选择套餐 -> 填写联系方式 -> 付款 -> 自动发卡/自动兑换。

【红线】
- 绝不透露货源、上游供应商、拿货渠道等任何信息。被问"你们货从哪来"一律回：官方渠道拿货，具体不方便透露。
- 只回答店铺商品、价格、下单、发货、售后相关问题；其他话题（闲聊、写作业、通用知识）礼貌拒绝。
- 不确定的事不要编，直接说"这个我不确定"，并引导加人工客服。
- 需要人工帮助时，给出人工客服微信：WECHAT_PLACEHOLDER
`;

// ---------- 供应商链（顺序=优先级），全走"有 Key 才启用" ----------
// Cloudflare Workers AI 走原生绑定（部署时加 AI 绑定，变量名 AI），无需 Key；
// 免费 1 万 neurons/天，超限直接报错 -> 自动降级到下一家（免费版不会扣费）。
function buildChain(env) {
  const chain = [];
  if (env.AI) {
    chain.push({ id: "cloudflare", kind: "cf", model: env.CF_MODEL || "@cf/meta/llama-3.3-70b-instruct" });
  }
  const openai = [
    // Agnes：OpenAI 兼容，flash 系列官方 $0/1M tokens 不限期免费（免费档 RPM<=20）
    { id: "agnes",     base: env.AGNES_BASE   || "https://apihub.agnes-ai.cn/v1", key: env.AGNES_KEY,   model: env.AGNES_MODEL   || "agnes-2.5-flash" },
    { id: "groq",      base: env.GROQ_BASE    || "https://api.groq.com/openai/v1", key: env.GROQ_KEY,    model: env.GROQ_MODEL    || "llama-3.3-70b-versatile" },
    { id: "gemini",    base: env.GEMINI_BASE  || "https://generativelanguage.googleapis.com/v1beta/openai/", key: env.GEMINI_KEY, model: env.GEMINI_MODEL || "gemini-2.5-flash" },
    // MiniMax：免费试用到 2026-11-07，之后按量计费（到期前记得换顺序或下掉）
    { id: "minimax",   base: env.MINIMAX_BASE || "https://api.minimax.io/v1", key: env.MINIMAX_KEY,     model: env.MINIMAX_MODEL || "MiniMax-M2" },
    { id: "sensenova", base: env.SENNOVA_BASE || "https://token.sensenova.cn/v1", key: env.SENNOVA_KEY, model: env.SENNOVA_MODEL || "sensenova-6.8-flash-lite" },
    { id: "kimi",      base: env.KIMI_BASE    || "https://api.moonshot.cn/v1", key: env.KIMI_KEY,        model: env.KIMI_MODEL    || "kimi-k2-0711-preview" },
  ];
  for (const p of openai) if (p.key) chain.push({ ...p, kind: "openai" });
  // 可用 PROVIDER_ORDER 环境变量自定义顺序，如 "cloudflare,agnes,minimax"
  if (env.PROVIDER_ORDER) {
    const order = env.PROVIDER_ORDER.split(",").map(s => s.trim());
    chain.sort((a, b) => order.indexOf(a.id) - order.indexOf(b.id));
  }
  return chain;
}

// ---------- 简易限流：防同行/脚本刷爆免费额度（他明确怕被攻击） ----------
// 同一 IP 10 分钟内最多 30 次对话；内存级，Worker 重启会重置，够用
const ipHits = new Map();
function rateLimited(ip) {
  const now = Date.now(), WINDOW = 10 * 60 * 1000, MAX = 30;
  let rec = ipHits.get(ip);
  if (!rec || now - rec.start > WINDOW) { rec = { start: now, count: 0 }; ipHits.set(rec && rec.start ? ip : ip, rec); }
  ipHits.set(ip, rec);
  rec.count++;
  return rec.count > MAX;
}

// 供应商熔断：失败后冷却 5 分钟再试
const downUntil = new Map();
function isDown(id) { return (downUntil.get(id) || 0) > Date.now(); }
function markDown(id) { downUntil.set(id, Date.now() + 5 * 60 * 1000); }

async function fetchTimeout(url, opts, ms) {
  const c = new AbortController();
  const t = setTimeout(() => c.abort(), ms);
  try {
    return await fetch(url, { ...opts, signal: c.signal });
  } finally {
    clearTimeout(t);
  }
}

async function callOpenAI(p, messages) {
  const res = await fetchTimeout(p.base.replace(/\/$/, "") + "/chat/completions", {
    method: "POST",
    headers: { "Authorization": "Bearer " + p.key, "Content-Type": "application/json" },
    body: JSON.stringify({ model: p.model, messages, max_tokens: 400, temperature: 0.3 }),
  }, 25000);
  if (!res.ok) throw new Error(p.id + " http " + res.status);
  const j = await res.json();
  const text = j.choices && j.choices[0] && j.choices[0].message && j.choices[0].message.content;
  if (!text) throw new Error(p.id + " empty");
  return text.trim();
}

// 允许的跨域来源：他的两个站 + 本地调试。买了自定义域名记得加进来。
const ALLOWED_ORIGINS = [
  "https://shop.qlinghl.workers.dev",
  "https://qlinghl.alwaysdata.net",
  "http://localhost",
];
function corsHeaders(req) {
  const origin = req.headers.get("Origin") || "";
  const allow = ALLOWED_ORIGINS.some(o => origin === o || origin.startsWith(o + ":"))
    ? origin : ALLOWED_ORIGINS[0];
  return {
    "Access-Control-Allow-Origin": allow,
    "Access-Control-Allow-Methods": "POST, GET, OPTIONS",
    "Access-Control-Allow-Headers": "Content-Type",
    "Content-Type": "application/json; charset=utf-8",
  };
}

export default {
  async fetch(req, env) {
    const headers = corsHeaders(req);
    if (req.method === "OPTIONS") return new Response(null, { headers });
    const url = new URL(req.url);

    if (url.pathname === "/api/health" && req.method === "GET") {
      const chain = buildChain(env);
      return new Response(JSON.stringify({
        ok: true,
        providers: chain.map(p => ({ id: p.id, up: !isDown(p.id) })),
      }), { headers });
    }

    if (url.pathname === "/api/chat" && req.method === "POST") {
      const ip = req.headers.get("CF-Connecting-IP") || "unknown";
      if (rateLimited(ip)) {
        return new Response(JSON.stringify({ error: "问得太快了，休息一下再来吧" }), { status: 429, headers });
      }
      let body;
      try { body = await req.json(); } catch (e) { body = {}; }
      const userMsgs = Array.isArray(body.messages) ? body.messages.slice(-6) : [];
      const lastUser = [...userMsgs].reverse().find(m => m.role === "user");
      if (!lastUser || !String(lastUser.content || "").trim()) {
        return new Response(JSON.stringify({ error: "先说句话吧" }), { status: 400, headers });
      }
      const messages = [{ role: "system", content: SHOP_KNOWLEDGE }, ...userMsgs];
      const chain = buildChain(env);
      const errors = [];
      for (const p of chain) {
        if (isDown(p.id)) continue;
        try {
          let reply;
          if (p.kind === "cf") {
            const r = await env.AI.run(p.model, { messages, max_tokens: 400 });
            reply = r && r.response;
            if (!reply) throw new Error("cf binding empty");
          } else {
            reply = await callOpenAI(p, messages);
          }
          return new Response(JSON.stringify({ reply, via: p.id }), { headers });
        } catch (e) {
          markDown(p.id);
          errors.push(p.id + ": " + (e && e.message));
        }
      }
      return new Response(JSON.stringify({
        error: "客服 AI 现在全都忙不过来，请稍后再试，或加人工客服微信：WECHAT_PLACEHOLDER",
        detail: errors.join(" | "),
      }), { status: 503, headers });
    }

    return new Response(JSON.stringify({ error: "not found" }), { status: 404, headers });
  },
};
