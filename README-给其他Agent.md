# 卡店前端源码包

给另一个 Agent 的说明：

## 目录结构
- `index.html` — 首页（商品卡片区，重点改这里）
- `ai.html` — AI 客服页
- `chatgpt.html` — ChatGPT 商品详情页
- `x-premium.html` — X Premium 商品详情页
- `tools/sidebar.html` — 左侧边栏源码（胶囊导航 + Claude 式设置弹窗）
- `tools/build.py` — 构建脚本（JS 混淆 + HTML/CSS 压缩 → `dist/`）
- `tools/add_sidebar.py` — 把侧边栏注入 4 个页面
- `logo.png` / `favicon.png` / `favicon.svg` / `robots.txt` — 静态资源

## 工作流
1. 直接改 4 个 HTML 源码（或 `tools/sidebar.html`）
2. `python3 tools/add_sidebar.py`（如果改了侧边栏）
3. `python3 tools/build.py` 生成 `dist/`
4. `cp logo.png favicon.png robots.txt dist/`
5. 部署：Cloudflare Dashboard → Workers & Pages → shop 项目 → 上传 `dist/` 内 8 个文件

## 当前线上
https://shop.qlinghl.workers.dev （Cloudflare Workers 静态托管）

## 已知注意点（别踩坑）
- `index.html` 里有多处 `@media(max-width:760px)`，改移动端样式前全局搜一遍，旧规则会覆盖新规则
- `tools/sidebar.html` 开头自带 `<!-- SHOP-SIDEBAR -->` 标记，`add_sidebar.py` 已修好不会重复注入，跑完数一下标记数
- 侧边栏移动端 CSS 里 `body.has-shop-sidebar{padding-left:20px}` 别改成 0，否则页面贴左没边距
- 卡片视觉（`.fa-gpt-card` 238×146px）在小屏下用 `transform:scale()` 缩放，别用 `scale` 独立属性（会和浮动动画的 `transform` 打架导致偏右）
- 构建产物 `dist/` 别直接改，每次构建会覆盖
