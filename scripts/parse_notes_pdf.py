#!/usr/bin/env python3
"""从 hibenba 夸克英语笔记 PDF 提取结构化单词 + 语法文本
格式: 第1页 "与课文关联的 N个单词" 之后的 word /音标/ 词性.释义 块
输出: {"words": [...], "grammar_text": "..."}
"""
import fitz, re, json, os, glob

def extract_pdf_words(pdf_path):
    try:
        d = fitz.open(pdf_path)
    except Exception:
        return {'words': [], 'grammar': []}
    text = '\n'.join(d[i].get_text() for i in range(len(d)))
    lines = [l.strip() for l in text.split('\n')]

    # ===== 1. 单词区: "与课文关联的 N个单词" ~ "课文理解" =====
    words = []
    try:
        start = next(i for i, l in enumerate(lines) if '与课文关联的' in l and '单词' in l)
    except StopIteration:
        start = -1
    end = len(lines)
    for i in range(start + 1, len(lines)):
        if '课文理解' in lines[i] or '课文引入' in lines[i]:
            end = i; break
    if start >= 0:
        seg = lines[start + 1:end]
        cur_word = None
        pending_ipa = None
        pending_def = None
        for l in seg:
            if l in ('*', '＊', ''):
                continue
            # 布局1: word / 音标 / 词性. 释义 同一行
            m = re.match(r'^([A-Za-z][A-Za-z\-\' ]*?)\s*/\s*([^/]+?)\s*/\s*([a-zA-Z.]+)\.?\s*(.*)$', l)
            if m:
                w = m.group(1).strip()
                ipa = '/' + m.group(2).strip() + '/'
                pos = m.group(3).strip()
                defn = m.group(4).strip()
                if w and w not in [x['w'] for x in words]:
                    words.append({'w': w.lower(), 'ipa': ipa, 'pos': pos, 'def': defn})
                cur_word = None
                continue
            # 布局2: word / 音标 /  (词性释义在下一行)
            m = re.match(r'^([A-Za-z][A-Za-z\-\' ]*?)\s*/\s*([^/]+?)\s*/\s*$', l)
            if m:
                w = m.group(1).strip()
                if w and w not in [x['w'] for x in words]:
                    words.append({'w': w.lower(), 'ipa': '/' + m.group(2).strip() + '/', 'pos': '', 'def': ''})
                cur_word = None
                continue
            # 布局3: word (独立行, 下一行是 /音标/)
            m = re.match(r'^([A-Za-z][A-Za-z\-\' ]{1,20})$', l)
            if m and len(l) < 25 and not re.search(r'[中文]', l):
                cur_word = l.lower()
                continue
            # 布局3b: / 音标 / 词性. 释义 (承接上一行 word)
            m2 = re.match(r'^/\s*([^/]+?)\s*/\s*(?:([a-zA-Z.]+)\.?\s*(.*))?$', l)
            if m2 and cur_word:
                if not any(x['w'] == cur_word for x in words):
                    words.append({'w': cur_word, 'ipa': '/' + m2.group(1).strip() + '/',
                                  'pos': (m2.group(2) or '').strip(), 'def': (m2.group(3) or '').strip()})
                cur_word = None
                continue
            # 布局3c: 词性. 释义 (承接上一行 word 或 音标行)
            m3 = re.match(r'^([a-zA-Z.]+)\.\s*(.+)$', l)
            if m3 and words:
                last = words[-1]
                # 若上一个词缺释义且 l 以词性开头, 且当前没有更近的词
                if last.get('def') == '' and not last.get('pos'):
                    last['pos'] = m3.group(1)
                    last['def'] = m3.group(2)
                elif last.get('pos') and not last.get('def'):
                    last['def'] = m3.group(2)
                cur_word = None
                continue
            cur_word = None

    # ===== 2. 语法: 含语法关键字的段落 =====
    grammar = []
    keywords = ['语法', '句型', '主谓', '时态', '从句', '句型结构', '语法知识']
    for i, l in enumerate(lines):
        if any(k in l for k in keywords) and 2 < len(l) < 60:
            # 收集该标题后的 2-4 行内容
            body = []
            for j in range(i + 1, min(i + 5, len(lines))):
                if len(lines[j]) > 3 and not re.match(r'^\s*$', lines[j]):
                    body.append(lines[j])
                else:
                    break
            if body:
                grammar.append({'title': l[:40], 'body': '\n'.join(body)[:300]})
    return {'words': words, 'grammar': grammar[:8]}

if __name__ == '__main__':
    import sys
    r = extract_pdf_words(sys.argv[1])
    print(f"words: {len(r['words'])}")
    for w in r['words'][:5]:
        print(f"  {w['w']} {w['ipa']} {w['pos']} {w['def'][:30]}")
    print(f"grammar: {len(r['grammar'])}")
    for g in r['grammar'][:3]:
        print(f"  - {g['title']}: {g['body'][:60]}")
