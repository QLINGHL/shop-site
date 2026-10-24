#!/usr/bin/env python3
"""从前端 HTML 源码提取商品文字，重新生成 knowledge.txt
用法：python3 tools/update_knowledge.py
输出：~/workspace/shop-api/knowledge.txt
"""
import re, os, html as htmllib

SRC = '/home/hatch/workspace/shop-deploy'
OUT = '/home/hatch/workspace/shop-api/knowledge.txt'
# 只提取这几个页面的正文（跳过 sidebar、script、style）
PAGES = {
    'index.html': '首页 index.html',
    'chatgpt.html': 'ChatGPT 详情页 chatgpt.html',
    'x-premium.html': 'X Premium 详情页 x-premium.html',
}

def extract_text(page):
    p = os.path.join(SRC, page)
    s = open(p, encoding='utf-8').read()
    # 去掉 sidebar 注入块
    s = re.sub(r'<!-- SHOP-SIDEBAR -->.*?</script>', '', s, flags=re.S)
    # 去掉所有 script 和 style
    s = re.sub(r'<script.*?</script>', '', s, flags=re.S)
    s = re.sub(r'<style.*?</style>', '', s, flags=re.S)
    # 去掉注释
    s = re.sub(r'<!--.*?-->', '', s, flags=re.S)
    # 取 body
    m = re.search(r'<body[^>]*>(.*)</body>', s, flags=re.S)
    if m:
        s = m.group(1)
    # 标签转行
    s = re.sub(r'<br\s*/?>', '\n', s)
    s = re.sub(r'</(p|div|h1|h2|h3|h4|li|tr|section|article)>', '\n', s)
    s = re.sub(r'<[^>]+>', '', s)
    s = htmllib.unescape(s)
    # 清理空白行和重复
    lines = []
    seen = set()
    for ln in s.split('\n'):
        ln = re.sub(r'\s+', ' ', ln).strip()
        if len(ln) < 2:
            continue
        # 跳过防抄版权声明（给 AI 爬虫看的，不进客服知识库）
        if 'AI AGENT NOTICE' in ln or '盗用必究' in ln or '版权所有' in ln:
            continue
        if ln in seen:
            continue
        seen.add(ln)
        lines.append(ln)
    return '\n'.join(lines)

parts = ['# 店铺知识库（构建时从页面文字自动提取）', '']
for page, title in PAGES.items():
    parts.append(f'## {title}')
    parts.append(extract_text(page))
    parts.append('')

open(OUT, 'w', encoding='utf-8').write('\n'.join(parts))
print(f'已生成 {OUT} ({os.path.getsize(OUT)} 字节)')
