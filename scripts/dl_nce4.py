#!/usr/bin/env python3
"""下载 NCE4 全部 LRC + 音频 (数据补齐)"""
import os, json, subprocess, urllib.parse, concurrent.futures

PROXY = 'http://127.0.0.1:7890'
BASE = 'https://nce.mleo.site/NCE4'
LRC_OUT = '/data/.default/nce-site/data/lrc'
AUDIO_OUT = '/data/.default/nce-site/data/audio'
os.makedirs(LRC_OUT, exist_ok=True)
os.makedirs(AUDIO_OUT, exist_ok=True)

def fetch(url, retries=3):
    for i in range(retries):
        r = subprocess.run(['curl', '-s', '--proxy', PROXY, '--max-time', '40', url], capture_output=True, text=True)
        if r.stdout.strip():
            return r.stdout
    return ''

book_path = '/tmp/nce4_book.json'
if os.path.exists(book_path) and os.path.getsize(book_path) > 100:
    data = json.load(open(book_path))
else:
    raw = fetch(f'{BASE}/book.json')
    data = json.loads(raw)
    json.dump(data, open(book_path, 'w'))
units = data['units']
print(f'NCE4 units: {len(units)}')

tasks = []
for i, u in enumerate(units, 1):
    enc = urllib.parse.quote(u['filename'])
    lrc_dest = f'{LRC_OUT}/NCE4-{i:03d}.lrc'
    mp3_dest = f'{AUDIO_OUT}/NCE4-{i:03d}.mp3'
    if not os.path.exists(lrc_dest) or os.path.getsize(lrc_dest) < 100:
        tasks.append((f'{BASE}/{enc}.lrc', lrc_dest))
    if not os.path.exists(mp3_dest) or os.path.getsize(mp3_dest) < 10000:
        tasks.append((f'{BASE}/{enc}.mp3', mp3_dest))

print(f'to download: {len(tasks)}')

def dl(t):
    url, dest = t
    try:
        subprocess.run(['curl', '-s', '--proxy', PROXY, '--max-time', '180', '-o', dest, url], capture_output=True)
        ok = os.path.exists(dest) and os.path.getsize(dest) > 100
        if not ok and os.path.exists(dest):
            os.remove(dest)
        return ok
    except Exception:
        return False

with concurrent.futures.ThreadPoolExecutor(max_workers=8) as ex:
    results = list(ex.map(dl, tasks))
print('OK:', sum(results), '/', len(tasks))
