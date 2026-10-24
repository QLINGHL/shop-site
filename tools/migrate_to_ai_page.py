#!/usr/bin/env python3
"""移除三页的悬浮球客服组件，改为独立 ai.html 入口按钮。
- 删除 <!-- SHOP-AI-CHAT --> 到最后一个 </script> 的整段
- index.html：在 sh-theme 前加 AI 入口
- chatgpt.html / x-premium.html：在 buy-header 的 sh-theme 前加 AI 入口
"""
import re, os

SRC = '/home/hatch/workspace/shop-deploy'
MARK = '<!-- SHOP-AI-CHAT -->'

AI_BTN_CSS = '''<style>.shop-ai-entry{display:inline-flex;align-items:center;gap:7px;min-height:38px;padding:0 16px;border:0;border-radius:999px;background:linear-gradient(135deg,var(--accent,#12a89a),#67dfd4);color:#fff;font:700 13px/1 var(--font-body,inherit);text-decoration:none;box-shadow:0 10px 25px rgba(18,168,154,.25);cursor:pointer;white-space:nowrap;transition:transform .25s,box-shadow .25s}.shop-ai-entry:hover{transform:translateY(-2px);box-shadow:0 14px 30px rgba(18,168,154,.35)}.shop-ai-entry svg{width:16px;height:16px;fill:#fff}</style>'''
AI_BTN = '''<a class="shop-ai-entry" href="ai.html"><svg viewBox="0 0 24 24"><path d="M12 2l2.4 7.2H22l-6 4.6 2.3 7.2-6.3-4.5-6.3 4.5L8 13.8 2 9.2h7.6z"/></svg>AI 客服</a>'''

for page in ['index.html', 'chatgpt.html', 'x-premium.html']:
    p = os.path.join(SRC, page)
    html = open(p, encoding='utf-8').read()

    # 1. 删除悬浮球组件
    if MARK in html:
        start = html.index(MARK)
        end = html.index('</script>', start) + len('</script>')
        html = html[:start] + html[end:]
        print(page, '悬浮球已删除')
    else:
        print(page, '无悬浮球标记')

    # 2. 加 AI 入口按钮（幂等）
    if 'shop-ai-entry' in html and 'href="ai.html"' in html:
        print(page, '入口已存在，跳过')
    else:
        if '</head>' in html and '.shop-ai-entry{' not in html:
            html = html.replace('</head>', AI_BTN_CSS + '\n</head>', 1)
        # index.html：在 sh-theme div 前插入
        if page == 'index.html':
            pat = '<div class="sh-theme" role="group" aria-label="主题切换">'
            if pat in html:
                html = html.replace(pat, AI_BTN + pat, 1)
                print(page, '入口已加（首页标题栏）')
        else:
            # 详情页：在 buy-header 的 sh-theme 前插入
            pat = '<div class="sh-theme" role="group" aria-label="主题切换">'
            if pat in html:
                html = html.replace(pat, AI_BTN + pat, 1)
                print(page, '入口已加（buy-header）')

    open(p, 'w', encoding='utf-8').write(html)

print('done')
