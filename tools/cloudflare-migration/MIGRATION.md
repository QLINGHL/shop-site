# Cloudflare Pages 迁移手册（他选 A/B 就动手）

目标：把 qlinghl.alwaysdata.net 上的 3 个静态页搬到 Cloudflare Pages，
绑他自己的域名，同时拆掉"免费版禁商用"这个雷。

## 核验结论（2026-10-09 已查）

- Cloudflare Pages 免费版：允许商用（Vercel Hobby 明确禁商用，CF 不禁）、
  自定义域名 + 自动 SSL、无限带宽。结论：之前的说法站得住。
- GitHub 学生包：Namecheap 1 年免费 .me 域名，2026 年依然有效；
  要学生认证（学校邮箱或学生证照片），审核几天。
- 注意：CF Pages 不认 .htaccess。安全头用 `_headers` 文件（已备好），
  UA 屏蔽用 WAF 自定义规则（waf-rules.md 已备好）——覆盖面和现在一样甚至更强，
  但这是"翻译"不是"照搬"，部署后要实测一遍。

## 他要做的（只能他自己动手）

1. 注册 Cloudflare 账号（dash.cloudflare.com，邮箱+密码，他自己填）。
2. 域名（二选一）：
   - A. GitHub 学生包领 .me：education.github.com/pack → 申请学生认证
     （学校邮箱最快，没有就用学生证/在读证明照片）→ 通过后去 Namecheap 领 .me 域名
     （首年 $0，续费约 $10/年）。审核要几天，不着急。
   - B. 花十几块买 .top/.xyz：腾讯云/阿里云，支付宝微信直接付，
     要实名认证（1-3 天）。
3. 把 Cloudflare 给的两个 nameserver 填到域名注册商的 DNS 设置里
   （A 方案在 Namecheap 后台改，B 方案在腾讯云/阿里云改）。
4. Pages 项目里 Custom domains → 加他的域名 → SSL 自动配好。

## 我动手的部分（他一点头就做）

1. 改 `tools/protect.js` 的 ALLOW 白名单，加上他的新域名。
2. `cd ~/workspace/shop-deploy/tools && python3 build.py` 重新构建 dist。
3. 把 `_headers`（本目录已备好）放进部署包根目录。
4. 部署：Cloudflare 仪表盘 → Pages → Create application → Upload assets，
   把 dist/*.html、robots.txt、_headers 拖进去（文件都 <200KB，远低于 25MB 上限）。
   他若给我开 Cloudflare 账号权限，也可以用 wrangler 命令行推。
5. 按 waf-rules.md 建 WAF 规则 + 开 Bot Fight Mode（他账号里的操作，
   我可以接管浏览器替他点，或给他一步步截图指引）。
6. 实测：正常 UA → 200 完整渲染；GPTBot UA → 403；无头浏览器 → 白板；
   新域名打开正常，旧 alwaysdata 地址保留做备用。

## 搬完之后

- AlwaysData 上的站不动，留着当备用（封号风险还在，但不再是唯一入口）。
- robots.txt 照旧，防抄的 JS 混淆/域名锁定/反调试全部保留（静态文件，换个主机照样跑）。
- 以后更新页面：改 shop-deploy/*.html → build.py → 重新上传到 Pages（或接 Git 自动部署，另议）。
- ji8 后端对接、404 链接修复、收钱方案：不受影响，照常推进。
