#!/usr/bin/env python3
"""全站加左侧边栏：注入 sidebar.html，删除旧主题切换器。
- 4 个页面：index.html, chatgpt.html, x-premium.html, ai.html
- 删除 .sh-theme div（旧主题切换）
- 侧边栏插到 <body> 后
"""
import re, os

SRC = '/home/hatch/workspace/shop-deploy'
TOOLS = '/home/hatch/workspace/shop-deploy/tools'
PAGES = ['index.html', 'chatgpt.html', 'x-premium.html', 'ai.html', 'settings.html']
MARK = '<!-- SHOP-SIDEBAR -->'

with open(os.path.join(TOOLS, 'sidebar.html'), encoding='utf-8') as f:
    SIDEBAR = f.read()
assert SIDEBAR.startswith(MARK), 'sidebar.html 必须以 MARK 开头'

for page in PAGES:
    p = os.path.join(SRC, page)
    html = open(p, encoding='utf-8').read()
    orig = html

    # 1. 删除旧的 .sh-theme 主题切换 div
    # 匹配 <div class="sh-theme" ...>...</div>
    html = re.sub(r'<div class="sh-theme"[^>]*>.*?</div>', '', html, flags=re.S)
    # ai.html 的顶栏里可能有，同样处理（上面已覆盖）

    # 2. 删除旧主题 JS（ targeting .sh-theme 的那段）
    # 找到包含 "querySelectorAll('.sh-theme" 的 script 块
    def rm_old_theme_js(m):
        code = m.group(1)
        if ".sh-theme" in code and "shop-theme" in code:
            return ''  # 整段删除
        return m.group(0)
    html = re.sub(r'<script>(.*?)</script>', rm_old_theme_js, html, flags=re.S)

    # 3. 注入侧边栏（幂等）
    if MARK not in html:
        m = re.search(r'<body[^>]*>', html)
        if m:
            html = html[:m.end()] + '\n' + SIDEBAR + html[m.end():]
            print(page, '侧边栏已注入')
        else:
            print(page, '无 body 标签，跳过')
    else:
        # 已有：替换为新版
        start = html.index(MARK)
        # 找到侧边栏 script 结束
        end = html.index('</script>', start) + len('</script>')
        # 可能有多个 script，找最后一个属于侧边栏的（用下一个 <!-- 或 <div 定位太复杂，直接用标记长度估算）
        # 简单起见：从 MARK 到下一个 </aside> 后的 </script>
        aside_end = html.index('</aside>', start) + len('</aside>')
        script_end = html.index('</script>', aside_end) + len('</script>')
        html = html[:start] + SIDEBAR + html[script_end:]
        print(page, '侧边栏已更新')

    if html != orig:
        open(p, 'w', encoding='utf-8').write(html)

print('done')
