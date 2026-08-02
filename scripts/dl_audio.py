#!/usr/bin/env python3
"""并行下载全部 NCE 音频"""
import os, subprocess, urllib.parse, concurrent.futures, json

PROXY = 'http://127.0.0.1:7890'
BASE = 'https://nce.mleo.site'
OUT = '/data/.default/nce-site/data/audio'
os.makedirs(OUT, exist_ok=True)

def fetch(url):
    r = subprocess.run(['curl', '-s', '--proxy', PROXY, '--max-time', '40', url], capture_output=True, text=True)
    return r.stdout

tasks = []
for book, count in [('NCE1', 72), ('NCE2', 96), ('NCE3', 60)]:
    try:
        data = json.loads(fetch(f'{BASE}/{book}/book.json'))
    except Exception as e:
        print(f'ERR fetch {book}: {e}')
        continue
    for i, u in enumerate(data['units'], 1):
        dest = f'{OUT}/{book}-{i:03d}.mp3'
        if not os.path.exists(dest) or os.path.getsize(dest) < 10000:
            enc = urllib.parse.quote(u['filename'])
            tasks.append((f'{BASE}/{book}/{enc}.mp3', dest))

print(f'Total audio to download: {len(tasks)}')

def dl(t):
    url, dest = t
    try:
        r = subprocess.run(['curl', '-s', '--proxy', PROXY, '--max-time', '180', '-o', dest, url], capture_output=True)
        ok = os.path.exists(dest) and os.path.getsize(dest) > 10000
        if not ok and os.path.exists(dest):
            try: os.remove(dest)
            except: pass
        return ok
    except Exception as e:
        return False

with concurrent.futures.ThreadPoolExecutor(max_workers=8) as ex:
    results = list(ex.map(dl, tasks))

print('Audio OK:', sum(results), '/', len(tasks))
