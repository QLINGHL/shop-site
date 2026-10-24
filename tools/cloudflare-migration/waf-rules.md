# Cloudflare WAF 规则（替代 .htaccess 的爬虫屏蔽层）

免费版配额：WAF 自定义规则 5 条（够用 1 条）、User Agent Blocking 10 条。

## 规则 1：屏蔽 AI 爬虫 + 自动化工具 UA（1 条自定义规则搞定全部）

Security → WAF → Custom rules → Create rule
- 名称：`Block AI scrapers and automation tools`
- 表达式（粘贴即可）：

```
(http.user_agent contains "GPTBot") or
(http.user_agent contains "ChatGPT-User") or
(http.user_agent contains "OAI-SearchBot") or
(http.user_agent contains "ClaudeBot") or
(http.user_agent contains "anthropic-ai") or
(http.user_agent contains "CCBot") or
(http.user_agent contains "Google-Extended") or
(http.user_agent contains "PerplexityBot") or
(http.user_agent contains "Applebot-Extended") or
(http.user_agent contains "Bytespider") or
(http.user_agent contains "Meta-ExternalAgent") or
(http.user_agent contains "meta-externalagent") or
(http.user_agent contains "Amazonbot") or
(http.user_agent contains "cohere-ai") or
(http.user_agent contains "YouBot") or
(http.user_agent contains "Diffbot") or
(http.user_agent contains "img2dataset") or
(http.user_agent contains "Scrapy") or
(http.user_agent contains "python-requests") or
(http.user_agent contains "python-urllib") or
(http.user_agent contains "Wget") or
(http.user_agent contains "curl") or
(http.user_agent contains "HTTrack") or
(http.user_agent contains "aiohttp") or
(http.user_agent contains "axios") or
(http.user_agent contains "node-fetch") or
(http.user_agent contains "Go-http-client") or
(http.user_agent contains "Java/") or
(http.user_agent contains "libwww-perl")
```

- 动作：Block
- 说明：`contains` 不区分大小写，与 .htaccess 的 [NC] 等价，一条规则顶掉整段 RewriteCond。

## 规则 2（可选）：Bot Fight Mode

Security → Bots → 打开 **Bot Fight Mode**（免费）。
作用：挡已知恶意自动化浏览器，是对他"防 browser-use 抄 UI"那层的前端检测的补充。
注意：和他现在的 protect.js 前端检测不冲突，两层叠加。

## 规则 3（可选）：防刷限流

Security → WAF → Rate limiting rules。免费版配额说法不一（有说 1 条免费，有说付费才有），
到仪表盘看有没有入口再说，没有就跳过——他的站是纯静态，刷爆也烧不到钱，优先级低。

## 备忘

- 剩余 4 条自定义规则额度别乱用，留着以后加（比如被某个固定 IP 骚扰时加 IP 屏蔽）。
- User Agent Blocking（Security → WAF → Tools）是另一套 10 条配额，不用也行，
  上面自定义规则已覆盖；留着备用。
