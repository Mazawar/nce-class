#!/usr/bin/env python3
"""下载 hibenba/New-Concept-English 全四册逐课 PDF 笔记 (夸克英语笔记)
来源: https://github.com/hibenba/New-Concept-English
输出: /data/.default/nce-site/data/notes-pdf/{nce1,nce2,nce3,nce4}/LessonXX.pdf
"""
import os, json, re, subprocess, concurrent.futures, urllib.parse, time

PROXY = 'http://127.0.0.1:7890'
API = 'https://api.github.com/repos/hibenba/New-Concept-English/contents'
RAW = 'https://raw.githubusercontent.com/hibenba/New-Concept-English/main'
OUT = '/data/.default/nce-site/data/notes-pdf'
BOOKS = ['nce1', 'nce2', 'nce3', 'nce4']

def api(url, retries=4):
    for i in range(retries):
        r = subprocess.run(['curl', '-s', '--proxy', PROXY, '--max-time', '40', '-H', 'User-Agent: curl', url], capture_output=True, text=True)
        if r.stdout.strip() and not r.stdout.startswith('{'):
            return json.loads(r.stdout)
        if r.stdout.strip():
            try: return json.loads(r.stdout)
            except Exception: pass
        time.sleep(2)
    return None

os.makedirs(OUT, exist_ok=True)

tasks = []
for bk in BOOKS:
    d = api(f'{API}/{bk}')
    if not d: 
        print(f'ERR list {bk}')
        continue
    dest_dir = os.path.join(OUT, bk)
    os.makedirs(dest_dir, exist_ok=True)
    for f in d:
        if f.get('type') != 'file' or not f['name'].endswith('.pdf'):
            continue
        # 提取 Lesson 号
        m = re.search(r'Lesson\s*(\d+)', f['name'])
        num = int(m.group(1)) if m else 0
        dest = os.path.join(dest_dir, f'Lesson{num:03d}.pdf')
        if os.path.exists(dest) and os.path.getsize(dest) > 10000:
            continue
        url = f'{RAW}/{bk}/{urllib.parse.quote(f["name"])}'
        tasks.append((url, dest, f['name']))

print(f'to download: {len(tasks)}')

def dl(t):
    url, dest, name = t
    try:
        subprocess.run(['curl', '-s', '--proxy', PROXY, '--max-time', '120', '-L', '-o', dest, url], capture_output=True)
        ok = os.path.exists(dest) and os.path.getsize(dest) > 10000
        if not ok and os.path.exists(dest):
            os.remove(dest)
        return (ok, name)
    except Exception:
        return (False, name)

with concurrent.futures.ThreadPoolExecutor(max_workers=4) as ex:
    results = list(ex.map(dl, tasks))
ok = sum(1 for r in results if r[0])
print(f'OK: {ok}/{len(tasks)}')
for r in results:
    if not r[0]: print('FAIL:', r[1])
