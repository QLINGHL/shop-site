// shop-api-proxy: AI 客服后端反向代理
// 前端只调本 Worker，不暴露 AlwaysData 真实地址。
// 后端仅接受 Cloudflare 出口 IP 的请求，直接打后端地址会被 403。
const BACKEND = 'https://qlinghl.alwaysdata.net';
const FRONTEND = 'https://shop.qlinghl.workers.dev';
const SHOP_SECRET = 'Mb6P99Wjc0BpBWg9zGeBCsniLW5KFIvY5uMth67eHlE';

export default {
  async fetch(request, env) {
    const url = new URL(request.url);

    if (request.method === 'OPTIONS') {
      return new Response(null, {
        status: 204,
        headers: {
          'Access-Control-Allow-Origin': FRONTEND,
          'Access-Control-Allow-Headers': 'Content-Type, X-Admin-Key',
          'Access-Control-Allow-Methods': 'POST, GET, OPTIONS',
        },
      });
    }

    if (!url.pathname.startsWith('/api/')) {
      return new Response('Not found', { status: 404 });
    }

    const ip = request.headers.get('CF-Connecting-IP') || 'unknown';
    if (isRateLimited(ip)) {
      return json({ error: 'too fast', reply: '你问得太快了，休息 1 分钟再问我吧。' }, 429);
    }

    const headers = new Headers();
    headers.set('Content-Type', 'application/json');
    headers.set('X-Real-IP', ip);
    headers.set('X-Shop-Secret', SHOP_SECRET);
    // 采购管理接口的鉴权头：原样透传，后端校验
    const adminKey = request.headers.get('X-Admin-Key');
    if (adminKey) headers.set('X-Admin-Key', adminKey);

    let body = null;
    if (request.method === 'POST') {
      const raw = await request.text();
      if (raw.length > 8192) return json({ error: 'too large' }, 413);
      body = raw;
    }

    try {
      const resp = await fetch(BACKEND + url.pathname + url.search, {
        method: request.method,
        headers,
        body,
      });
      // 流式端点：直接透传 SSE 流，不缓冲
      if (url.pathname === '/api/chat/stream') {
        return new Response(resp.body, {
          status: resp.status,
          headers: {
            'Content-Type': 'text/event-stream; charset=utf-8',
            'Cache-Control': 'no-cache',
            'Access-Control-Allow-Origin': FRONTEND,
          },
        });
      }
      const data = await resp.text();
      return new Response(data, {
        status: resp.status,
        headers: {
          'Content-Type': 'application/json; charset=utf-8',
          'Access-Control-Allow-Origin': FRONTEND,
        },
      });
    } catch (e) {
      return json({ reply: '抱歉，AI 客服暂时开小差了，请稍后再试。' }, 503);
    }
  },
};

function json(obj, status) {
  return new Response(JSON.stringify(obj), {
    status: status || 200,
    headers: {
      'Content-Type': 'application/json; charset=utf-8',
      'Access-Control-Allow-Origin': FRONTEND,
    },
  });
}

const _hits = new Map();
function isRateLimited(ip, limit, windowSec) {
  limit = limit || 20; windowSec = windowSec || 60;
  const now = Date.now() / 1000;
  let arr = _hits.get(ip) || [];
  arr = arr.filter(function (t) { return now - t < windowSec; });
  if (arr.length >= limit) { _hits.set(ip, arr); return true; }
  arr.push(now);
  _hits.set(ip, arr);
  if (_hits.size > 5000) _hits.clear();
  return false;
}
