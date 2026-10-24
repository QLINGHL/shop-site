#!/usr/bin/env python3
"""给三个页面注入全店 AI 客服聊天悬浮窗（FAB + 聊天面板）。
组件源码: tools/chat_widget.html（含 __API_URL__ 占位符）
用法: python3 tools/add_chat.py  (幂等，已注入则跳过)
"""
import os

SRC = '/home/hatch/workspace/shop-deploy'
TOOLS = '/home/hatch/workspace/shop-deploy/tools'
PAGES = ['index.html', 'chatgpt.html', 'x-premium.html']
API_URL = 'https://qlinghl.alwaysdata.net/api/chat'
MARK = '<!-- SHOP-AI-CHAT -->'
OLD_MARK = '<!-- SHOP-AI-CHAT -->'

with open(os.path.join(TOOLS, 'chat_widget.html'), encoding='utf-8') as f:
    WIDGET = f.read().replace('__API_URL__', API_URL)

for page in PAGES:
    p = os.path.join(SRC, page)
    html = open(p, encoding='utf-8').read()
    if MARK in html:
        # 已有旧版：整段替换（从 MARK 到 </script> 后的第一个完整块）
        import re
        # 旧版 widget 从 MARK 开始到最后一个 </script> 结束
        start = html.index(MARK)
        end = html.index('</script>', start) + len('</script>')
        html = html[:start] + WIDGET + html[end:]
        open(p, 'w', encoding='utf-8').write(html)
        print(page, '旧版已替换为新版')
        continue
    if '</body>' not in html:
        print(page, '无 </body>，跳过'); continue
    html = html.replace('</body>', WIDGET + '\n</body>')
    open(p, 'w', encoding='utf-8').write(html)
    print(page, '注入完成')
