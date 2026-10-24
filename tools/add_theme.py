#!/usr/bin/env python3
"""给三个页面添加深色/浅色/跟随系统主题切换。"""
import re, os

SRC = '/home/hatch/workspace/shop-deploy'

DARK_CSS = """
/* ===== 深色主题 ===== */
.dark body.shop-tokens,.dark .shop-scope{--bg:#0b1120;--surface:#131b2e;--surface-2:#182136;--surface-3:#1f2940;--text:#e9eef6;--muted:#8f9ab2;--line:rgba(148,170,210,.13);--line-strong:rgba(148,170,210,.22);--accent:#2dd4bf;--accent-strong:#5eead4;--accent-soft:rgba(45,212,191,.12);--accent-line:rgba(45,212,191,.4);--on-accent:#03211c;--header:rgba(11,17,32,.9);--shadow:0 20px 55px rgba(0,0,0,.5);--shadow-soft:0 8px 28px rgba(0,0,0,.4);--shadow-mark:0 9px 22px rgba(45,212,191,.25);--shadow-primary:0 10px 25px rgba(45,212,191,.22);--shadow-pop:0 24px 70px rgba(0,0,0,.55);--ui-text-secondary:#b9c3d6;color-scheme:dark}
.dark .shop-scope .sh-fcard.is-x .fa-x-card{border:1px solid rgba(255,255,255,.14)}
/* ===== 主题切换开关 ===== */
.shop-scope .sh-theme{display:inline-flex;align-items:center;gap:2px;padding:3px;border:1px solid var(--line);border-radius:999px;background:var(--surface-2);flex:none}
.shop-scope .sh-theme button{appearance:none;-webkit-appearance:none;border:0;background:transparent;color:var(--muted);font:600 12px/1 var(--font-body);padding:7px 11px;border-radius:999px;cursor:pointer;white-space:nowrap}
.shop-scope .sh-theme button.is-on{background:var(--surface);color:var(--text);box-shadow:0 1px 5px rgba(8,15,30,.25)}
.shop-scope .buy-header .sh-theme{margin-left:auto}
@media(max-width:760px){.shop-scope .sh-theme button{padding:6px 9px;font-size:11px}}"""

THEME_HTML = """<div class="sh-theme" role="group" aria-label="主题切换"><button type="button" data-theme="light">浅色</button><button type="button" data-theme="dark">深色</button><button type="button" data-theme="auto">自动</button></div>"""

# 防闪烁：head 内最先执行
ANTI_FOUC = """<script>try{var _t=localStorage.getItem('shop-theme')||'auto';if(_t==='dark'||(_t==='auto'&&window.matchMedia&&matchMedia('(prefers-color-scheme:dark)').matches))document.documentElement.classList.add('dark')}catch(e){}</script>"""

THEME_JS = """<script>(function(){var K='shop-theme';function sysD(){return window.matchMedia&&matchMedia('(prefers-color-scheme:dark)').matches}function mode(){try{return localStorage.getItem(K)||'auto'}catch(e){return'auto'}}function apply(){var m=mode();var d=m==='dark'||(m==='auto'&&sysD());document.documentElement.classList.toggle('dark',d);var b=document.querySelectorAll('.sh-theme [data-theme]');for(var i=0;i<b.length;i++)b[i].classList.toggle('is-on',b[i].getAttribute('data-theme')===m)}function init(){apply();var b=document.querySelectorAll('.sh-theme [data-theme]');for(var i=0;i<b.length;i++)(function(x){x.addEventListener('click',function(){try{localStorage.setItem(K,x.getAttribute('data-theme'))}catch(e){}apply()})})(b[i]);var mq=window.matchMedia&&matchMedia('(prefers-color-scheme:dark)');if(mq){var f=function(){if(mode()==='auto')apply()};if(mq.addEventListener)mq.addEventListener('change',f);else if(mq.addListener)mq.addListener(f)}}if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',init);else init()})();</script>"""

def process(page, toggle_anchor, toggle_mode):
    p = os.path.join(SRC, page)
    html = open(p).read()
    orig = html

    # 1. 深色 CSS：追加到第一个 </style> 前
    if '/* ===== 深色主题 ===== */' not in html:
        html = html.replace('</style>', DARK_CSS + '</style>', 1)

    # 2. 防闪烁脚本：紧跟 <head>
    if 'shop-theme' not in html.split('</head>')[0] or '_t=localStorage' not in html:
        m = re.search(r'<head[^>]*>', html)
        html = html[:m.end()] + ANTI_FOUC + html[m.end():]

    # 3. 开关 HTML
    if 'data-theme="light"' not in html:
        if toggle_mode == 'heading':
            # index.html：放到 sh-section-heading 内标题 div 之后
            pat = r'(<div class="sh-section-heading">\s*<div>.*?</div>)(\s*</div>)'
            mm = re.search(pat, html, re.S)
            assert mm, f'heading anchor not found in {page}'
            html = html[:mm.start(2)] + THEME_HTML + html[mm.start(2):]
        else:
            # 详情页：放到 buy-header 末尾，并让 header 两端对齐
            pat = r'(<header class="buy-header">.*?</a>)(\s*</header>)'
            mm = re.search(pat, html, re.S)
            assert mm, f'header anchor not found in {page}'
            html = html[:mm.start(2)] + THEME_HTML + html[mm.start(2):]
            # buy-header 改为两端对齐
            html = html.replace('.buy-header{display:flex;align-items:center;justify-content:flex-end;',
                                '.buy-header{display:flex;align-items:center;justify-content:space-between;gap:12px;', 1)

    # 4. 主题逻辑 JS：</body> 前
    if 'sh-theme [data-theme]' not in html.replace(ANTI_FOUC, ''):
        html = html.replace('</body>', THEME_JS + '</body>', 1)

    if html != orig:
        open(p, 'w').write(html)
        print(page, 'updated')
    else:
        print(page, 'no change')

process('index.html', None, 'heading')
process('chatgpt.html', None, 'header')
process('x-premium.html', None, 'header')
print('DONE')
