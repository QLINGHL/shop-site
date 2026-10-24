#!/usr/bin/env python3
"""构建前端版本：压缩HTML/CSS。
干净源码保留在 shop-deploy/，构建版本输出到 shop-deploy/dist/。
（2026-10-10：已移除全部防抄机制——protect.js 注入、JS 混淆，因误杀真实设备）"""
import re, subprocess, os, sys

SRC = '/home/hatch/workspace/shop-deploy'
DIST = '/home/hatch/workspace/shop-deploy/dist'
TOOLS = os.path.expanduser('~/workspace/shop-deploy/tools')
PAGES = ['index.html', 'chatgpt.html', 'x-premium.html', 'ai.html', 'settings.html']

os.makedirs(DIST, exist_ok=True)

def run(cmd):
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        print('FAILED:', ' '.join(cmd)); print(r.stderr[-2000:]); sys.exit(1)
    return r.stdout.strip()

for page in PAGES:
    html = open(f'{SRC}/{page}').read()
    orig_len = len(html)

    # 直接压缩 HTML（含 CSS），不注入任何保护脚本，不混淆
    tmp = f'{TOOLS}/{page}.tmp'
    open(tmp, 'w').write(html)
    run(['node', f'{TOOLS}/minhtml.js', tmp, f'{DIST}/{page}'])
    new_len = os.path.getsize(f'{DIST}/{page}')
    print(f'{page}: {orig_len} -> {new_len} bytes')

print('BUILD OK ->', DIST)
