#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
NCE 学习站 v2 数据构建器 (v3 重构版)
数据源 (优先级从高到低):
  1. LiDuoMiao notes 结构化笔记 (每课精选词汇+词组+语法+句型)  data/notes/{NCE1,NCE2,NCE3,NCE4}/*.json
  2. LRC 课文 (英中对照+时间轴+音频)   data/lrc/*.lrc
  3. 用户上传 Lesson PDF (详细讲义)    library/
  4. ECDICT 词典 (音标补充)            data/stardict.db
  5. NCE3/NCE4 docx 笔记               data/NCE3|NCE4/
  6. NCE2 迷你笔记 + NCE1 标准语法表   (兜底)
输出: /data/.default/nce-site/public/data/ (index.json + units/{nce1,nce2,nce3}/*.json + library.json)
"""
import os, re, json, glob, sys, random, sqlite3

LRC_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'data', 'lrc')
AUDIO_BASE = 'audio'
ECDB = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'data', 'stardict.db')
NOTES_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'data', 'notes')
NCE3_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'data', 'NCE3')
NCE4_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'data', 'NCE4')
NCE2_NOTE = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'data', 'NCE2', '新概念2迷你笔记.txt')
OUT_DIR = '/data/.default/nce-site/public/data'
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from nce1_grammar import NCE1_GRAMMAR

BOOKS = [
    ('nce1', '新概念英语第一册', 'NCE1', 72, 1),
    ('nce2', '新概念英语第二册', 'NCE2', 48, 2),
    ('nce3', '新概念英语第三册', 'NCE3', 30, 3),
    ('nce4', '新概念英语第四册', 'NCE4', 24, 4),
]

# ========== 0. LiDuoMiao notes 加载 ==========
def load_notes():
    """加载结构化笔记: (book_key, key_id) -> {vocab, phrases, grammar, sentencePatterns}
    NCE1 文件名 001-002.json = 单元1 (含两课, 单元粒度); NCE2/3/4 文件名 01.json = 第1课 (课粒度)"""
    notes = {}
    for book_key, label, prefix, count, level in BOOKS:
        d = os.path.join(NOTES_DIR, prefix)
        if not os.path.isdir(d): continue
        for f in glob.glob(os.path.join(d, '*.json')):
            base = os.path.basename(f)
            if base == 'index.json': continue
            try:
                data = json.load(open(f, encoding='utf-8'))
            except Exception:
                continue
            if book_key == 'nce1':
                m = re.match(r'^(\d+)-(\d+)\.json$', base)
                unit_id = (int(m.group(1)) + 1) // 2 if m else None
                if unit_id is None or unit_id < 1 or unit_id > count: continue
                notes[(book_key, unit_id)] = data
            else:
                m = re.match(r'^(\d+)\.json$', base)
                lesson = int(m.group(1)) if m else None
                if lesson is None or lesson < 1 or lesson > count * 2: continue
                notes[(book_key, lesson)] = data
    return notes

def merge_notes(n1, n2):
    """合并两课笔记(课粒度 -> 单元): vocabulary/phrases/grammar/sentencePatterns 拼接去重"""
    if not n1: return n2
    if not n2: return n1
    out = dict(n1)
    for k in ('vocabulary', 'phrases', 'grammar', 'sentencePatterns'):
        a = n1.get(k) or []
        b = n2.get(k) or []
        if k == 'vocabulary':
            seen = {v.get('word','') for v in a}
            merged = list(a)
            for v in b:
                if v.get('word','') not in seen:
                    merged.append(v); seen.add(v.get('word',''))
        else:
            seen = set()
            merged = []
            for item in a + b:
                key = json.dumps(item, ensure_ascii=False, sort_keys=True)
                if key not in seen:
                    seen.add(key); merged.append(item)
        out[k] = merged
    return out

def merge_docx(d1, d2):
    """合并两课 docx 笔记: words/grammar/sentences 拼接去重"""
    if not d1: return d2
    if not d2: return d1
    out = dict(d1)
    seen_w = {w['w'] for w in d1.get('words', [])}
    merged_w = list(d1.get('words', []))
    for w in d2.get('words', []):
        if w['w'] not in seen_w:
            merged_w.append(w); seen_w.add(w['w'])
    out['words'] = merged_w
    seen_g = set()
    merged_g = []
    for g in (d1.get('grammar', []) + d2.get('grammar', [])):
        if g not in seen_g:
            seen_g.add(g); merged_g.append(g)
    out['grammar'] = merged_g
    seen_s = set()
    merged_s = []
    for s in (d1.get('sentences', []) + d2.get('sentences', [])):
        if s not in seen_s:
            seen_s.add(s); merged_s.append(s)
    out['sentences'] = merged_s
    return out

def note_vocab_to_list(data):
    """notes vocabulary -> [{w,ipa,pos,def,note}]"""
    out = []
    for v in data.get('vocabulary', []) or []:
        w = (v.get('word') or '').strip().lower()
        if not w or not w.isalpha(): continue
        ipa = v.get('phonetic') or ''
        meanings = v.get('meanings') or []
        if meanings:
            pos = meanings[0].get('pos', '')
            defs = '；'.join([m.get('meaning','') for m in meanings if m.get('meaning')])
            note_lines = []
            for m in meanings:
                if m.get('usage'):
                    note_lines.append(f"{m.get('pos','')} {m.get('meaning','')}: {m.get('usage','')}")
            note = '\n'.join(note_lines[:8])
        else:
            pos, defs, note = '', '', ''
        out.append({'w': w, 'ipa': ipa, 'pos': pos, 'def': defs, 'note': note})
    return out

POS_MAP = {
    'n': '名词', 'v': '动词', 'vt': '及物动词', 'vi': '不及物动词', 'adj': '形容词',
    'a': '形容词', 'adv': '副词', 'ad': '副词', 'prep': '介词', 'pron': '代词',
    'conj': '连词', 'num': '数词', 'art': '冠词', 'int': '感叹词', 'aux': '助动词',
    'r': '副词', 'j': '形容词', 'o': '代词', 'd': '限定词', 'p': '介词', 'c': '连词',
    'u': '感叹词', 'm': '数词',
}

def norm_ipa(raw):
    """ECDICT 音标转标准 IPA 格式: 'bju:tiful -> /ˈbjuːtɪfʊl/"""
    if not raw:
        return ''
    s = raw.strip().strip('/')
    if not s:
        return ''
    s = s.replace(':', 'ː').replace("'", 'ˈ')
    # 双重音: 次重音 , 转 ˌ
    s = s.replace(',', 'ˌ')
    return '/' + s + '/'

def norm_pos(raw):
    """ECDICT pos 字段 'n:100/j:1' -> '名词'"""
    if not raw:
        return ''
    parts = raw.split('/')
    best = ''
    for p in parts:
        m = re.match(r'([a-z]+):(\d+)', p.strip())
        if m:
            key, weight = m.group(1), int(m.group(2))
            if key in POS_MAP and (not best or weight > 0):
                best = key
    return POS_MAP.get(best, best)

def norm_def(translation, pos_raw):
    """从 ECDICT 多行释义取主释义, 合并词性"""
    if not translation:
        return ''
    lines = [l.strip() for l in translation.split('\n') if l.strip()]
    if not lines:
        return ''
    first = lines[0]
    # 去掉词性前缀 (n. / vt. 等)
    first = re.sub(r'^[a-zA-Z.]+\s+', '', first)
    if len(lines) > 1:
        extras = []
        for l in lines[1:]:
            e = re.sub(r'^\[.*?\]\s*', '', l)
            e = re.sub(r'^[a-zA-Z.]+\s+', '', e)
            if e and e not in extras:
                extras.append(e)
        if extras:
            return first + '；' + '；'.join(extras[:2])
    return first

class ECDICT:
    def __init__(self, db_path):
        self.conn = sqlite3.connect(db_path)
        self.conn.row_factory = sqlite3.Row
        self.cur = self.conn.cursor()
        total = self.cur.execute('SELECT COUNT(*) FROM stardict').fetchone()[0]
        print(f'ECDICT 词典加载: {total} 词条')

    def get(self, word):
        """返回 {ipa,pos,def,collins,exchange} 或 None"""
        row = self.cur.execute(
            'SELECT phonetic, pos, translation, collins, exchange FROM stardict WHERE word=?', (word.lower(),)
        ).fetchone()
        if not row:
            return None
        return {
            'ipa': norm_ipa(row['phonetic']),
            'pos': norm_pos(row['pos']),
            'def': norm_def(row['translation'], row['pos']),
            'collins': row['collins'] or 0,
            'exchange': (row['exchange'] or '').strip(),
        }

    def close(self):
        self.conn.close()

# ========== LRC 解析 ==========
def parse_lrc(text):
    meta = {}
    lines = []
    for line in text.split('\n'):
        m = re.match(r'^\[(al|ar|ti|by|offset|length):(.*)\]$', line)
        if m:
            meta[m[1]] = m[2].strip(); continue
        lm = re.match(r'^\[(\d+):(\d+[.,]\d+)\](.*)$', line)
        if lm:
            sec = int(lm[1]); ms = float(lm[2].replace(',', '.'))
            content = lm[3].strip()
            parts = content.split('|')
            lines.append({
                'time': round((sec*60+ms)*1000),
                'en': (parts[0] or '').strip(),
                'zh': (parts[1] or '').strip(),
            })
    return meta, lines

STOPWORDS = set('''a an the and or but if then so of to in on at for with from by about into onto over under
i you he she it we they me him her us them my your his its our their mine yours
am is are was were be been being do does did done have has had will would shall should can could may might must
this that these those there here what who whom whose which when where why how not no yes all any some each every
as than up down out off away again once more most much many few little very too so such just only also
lesson listen tape answer question speak read write look sit stand come go put give take make
'''.split())

# 指令/标题行: 不提取词汇 (LRC 开头的 "Lesson X"、"Listen to the tape..." 等)
def is_instruction_line(en):
    e = en.strip().lower()
    if re.match(r'^lesson\s*\d+', e): return True
    if re.match(r'^listen to the tape', e): return True
    if re.match(r'^answer (this|the) question', e): return True
    if re.match(r'^read (this|the)', e): return True
    if re.match(r'^now answer', e): return True
    return False

def extract_vocab(en_lines):
    counts = {}
    for ln in en_lines:
        if is_instruction_line(ln): continue
        for w in re.findall(r"[A-Za-z']+", ln):
            w = w.lower().strip("'")
            if len(w) > 1 and w not in STOPWORDS:
                counts[w] = counts.get(w, 0) + 1
    order = []
    seen = set()
    for ln in en_lines:
        if is_instruction_line(ln): continue
        for w in re.findall(r"[A-Za-z']+", ln):
            w = w.lower().strip("'")
            if len(w) > 1 and w not in STOPWORDS and w not in seen:
                seen.add(w); order.append(w)
    return order, counts

# ========== NCE3/4 docx 笔记增强解析 ==========
def parse_docx_words(path):
    """提取词汇块: 词头行(word [ipa] pos. 释义) + 词组/例句/发音相似/同根词 作为 note; 语法段落单独提取"""
    import docx
    d = docx.Document(path)
    paras = [p.text.strip() for p in d.paragraphs if p.text.strip()]
    words = []
    grammar = []
    cur = None
    cur_note = []
    in_grammar = False
    grammar_buf = []
    for i, p in enumerate(paras):
        # 词头行: word [ipa] pos. 释义 或 word [ipa] pos 释义
        m = re.match(r'^([A-Za-z][A-Za-z\s\-]*?)\s*\[([^\]]+)\]\s*((?:n|v|vt|vi|adj|adv|prep|pron|conj|num|art|int|aux)\.?)\s*(.*)$', p)
        if not m:
            m = re.match(r'^([A-Za-z][A-Za-z\s\-]*?)\s*\[([^\]]+)\]\s*$', p)
        if m:
            if cur:
                cur['note'] = '\n'.join(cur_note[:40])[:1500]
                words.append(cur)
            word = m.group(1).strip()
            ipa = m.group(2).strip()
            pos = m.group(3).strip() if m.lastindex >= 3 else ''
            meaning = m.group(4).strip() if m.lastindex >= 4 else ''
            # 若释义在下一行
            if not meaning and i+1 < len(paras):
                nxt = paras[i+1]
                mm = re.match(r'^((?:n|v|vt|vi|adj|adv|prep|pron|conj|num|art|int|aux)\.?)\s*(.*)$', nxt)
                if mm:
                    pos = pos or mm.group(1); meaning = mm.group(2).strip()
            if word and word.isalpha():
                cur = {'w': word.lower(), 'ipa': ipa, 'pos': pos, 'def': meaning, 'note': ''}
                cur_note = []
            else:
                cur = None
            continue
        # 语法段落优先检测: "语法:"开头 或 语法术语行(排除词组/例句类)
        is_grammar = bool(re.match(r'^\s*语法[:：]', p)) or (
            bool(re.search(r'从句|时态|语态|非谓语|虚拟|宾语从句|定语从句|同位语从句|状语从句|主语从句', p))
            and not re.match(r'^(词组|短语|造句|例[:：]|发音|同义词|近义词|反义词|变形|搭配|使用|用法)', p)
            and len(p) > 10
        )
        if is_grammar:
            grammar.append(p[:300])
            continue
        if cur and p:
            cur_note.append(p)
            continue
    if cur:
        cur['note'] = '\n'.join(cur_note[:40])[:1500]
        words.append(cur)
    # 去重
    seen = set(); uniq = []
    for w in words:
        if w['w'] not in seen:
            seen.add(w['w']); uniq.append(w)
    return {'words': uniq, 'grammar': grammar[:12]}

# ========== NCE2 迷你笔记解析 ==========
def parse_nce2_note(path):
    text = open(path, encoding='utf-8').read()
    notes = {}
    current = None
    for line in text.split('\n'):
        m = re.match(r'^\(Lesson\)([\d-]+)', line.strip())
        if m:
            current = m.group(1)
            notes[current] = []
            continue
        if current and line.strip():
            s = line.strip().lstrip('0123456789.\t ')
            if s and not re.match(r'^[\d\s]+$', s):
                notes[current].append(s)
    return notes

# ========== 用户 Lesson PDF 解析 ==========
def parse_lesson_pdf(path):
    import subprocess, tempfile
    with tempfile.NamedTemporaryFile(suffix='.txt', delete=False, mode='w') as tf:
        tmp = tf.name
    subprocess.run(['pdftotext', path, tmp], check=True, capture_output=True)
    text = open(tmp, encoding='utf-8', errors='ignore').read()
    os.unlink(tmp)
    lines = [l.strip() for l in text.split('\n') if l.strip()]

    words = []
    grammar = []
    sentences = []
    i = 0
    part = 0
    while i < len(lines):
        line = lines[i]
        if re.match(r'^Part\d+', line):
            part = int(re.search(r'Part(\d+)', line).group(1))
            i += 1; continue
        m = re.match(r'^([A-Za-z][A-Za-z\s\-]*?)\s*[（(]?美[）)]?\s*/([^/]+)/\s*(?:（(?:美|英)[）)]?\s*/([^/]+)/\s*)?((?:n|v|adj|adv|prep|pron|conj|num|art|int|aux)\.?)\s*(.*)$', line)
        if not m:
            m = re.match(r'^([A-Za-z][A-Za-z\s\-]*?)\s*/([^/]+)/\s*((?:n|v|adj|adv|prep|pron|conj|num|art|int|aux)\.?)\s*(.*)$', line)
        if m and part == 1:
            word = m.group(1).strip()
            ipa = f"/{m.group(2)}/"
            pos = m.group(4) if m.lastindex >= 4 else ''
            meaning = m.group(5) if m.lastindex >= 5 else ''
            note_lines = []
            j = i + 1
            while j < len(lines):
                nl = lines[j]
                if re.match(r'^Part\d+', nl): break
                if re.match(r'^[A-Za-z][A-Za-z\s\-]*?\s*[（(]?美[）)]?\s*/([^/]+)/', nl) or re.match(r'^[A-Za-z][A-Za-z\s\-]*?\s*/([^/]+)/', nl):
                    break
                note_lines.append(nl)
                j += 1
            if word:
                words.append({'w': word.lower(), 'ipa': ipa, 'pos': pos, 'def': meaning,
                              'note': '\n'.join(note_lines[:20])[:600]})
            i = j
            continue
        if part == 2 and re.search(r'[a-zA-Z]{3,}', line) and re.search(r'[\u4e00-\u9fff]', line):
            sentences.append(line)
        if part == 2 and re.search(r'[\u4e00-\u9fff]', line) and re.search(r'(句型|用法|结构|形式|否定|疑问|比较|时态|语态|从句|主格|宾格|人称|复数|动词|名词|形容词|副词|介词|连词|代词|冠词)', line):
            grammar.append(line[:200])
        i += 1
    seen = set(); uniq = []
    for w in words:
        if w['w'] not in seen:
            seen.add(w['w']); uniq.append(w)
    return {'words': uniq, 'grammar': grammar[:10], 'sentences': sentences[:15]}

# ========== 训练题生成 (增强版) ==========
def gen_quiz(unit_title, en_lines, zh_lines, vocab, ecd, book_level):
    quizzes = []
    random.seed(unit_title)
    # 过滤有效句子（英文长度足够且非空，排除指令/标题行）
    valid = [(en, zh) for en, zh in zip(en_lines, zh_lines) if len(en) > 8 and not is_instruction_line(en)]
    if not valid:
        return quizzes

    # --- 1. 词汇选择题 (用 ECDICT 真实释义) ---
    q_words = [w for w in vocab if w.get('def') and len(w.get('w','')) >= 3]
    random.shuffle(q_words)
    for w in q_words[:6]:
        word = w['w']
        correct = w['def'].split('；')[0][:40]
        # 干扰项: 从其他单元词义随机取 (保证真实词义)
        pool = [v['def'].split('；')[0][:40] for v in vocab if v.get('def') and v['def'] != w['def']]
        extras = []
        for v2 in vocab:
            if len(extras) >= 2: break
            if v2.get('def') and v2['w'] != word and v2['def'].split('；')[0][:40] not in pool:
                pool.append(v2['def'].split('；')[0][:40])
        distractors = random.sample([d for d in pool if d and d != correct and len(d) > 1], 3) if len(pool) >= 3 else []
        if len(distractors) < 3: continue
        opts = [correct] + distractors
        random.shuffle(opts)
        quizzes.append({
            'type': 'choice', 'q': f"「{word}」的意思是？",
            'opts': opts, 'answer': chr(65 + opts.index(correct)),
            'explain': f"{word} {w.get('ipa','')} {w.get('pos','')} {w.get('def','')}"
        })
        if len(quizzes) >= 3: break

    # --- 2. 挖空题 (课文关键实词) ---
    random.shuffle(valid)
    for en, zh in valid[:8]:
        words_in = re.findall(r"[A-Za-z']+", en)
        candidates = [w for w in words_in if len(w) >= 4 and w.lower() not in STOPWORDS]
        if not candidates: continue
        pick = random.choice(candidates)
        blank = re.sub(rf'\b{re.escape(pick)}\b', '______', en, count=1)
        if '______' not in blank: continue
        quizzes.append({
            'type': 'fill', 'q': blank,
            'opts': [], 'answer': pick,
            'explain': f"原文：{en}\n译文：{zh}"
        })
        if len(quizzes) >= 5: break

    # --- 3. 翻译题 (中→英) ---
    for en, zh in valid[:4]:
        quizzes.append({
            'type': 'trans', 'q': zh,
            'opts': [], 'answer': en,
            'explain': f"参考：{en}"
        })
        if len(quizzes) >= 8: break
    return quizzes[:8]

# ========== 主流程 ==========
def main():
    ecd = ECDICT(ECDB)

    docx_cache = {}
    nce3_files = sorted(glob.glob(f'{NCE3_DIR}/*.docx'), key=lambda f: int(re.search(r'Lesson\s*(\d+)', f).group(1)))
    for f in nce3_files:
        num = int(re.search(r'Lesson\s*(\d+)', f).group(1))
        docx_cache[('nce3', num)] = parse_docx_words(f)
    nce4_files = sorted(glob.glob(f'{NCE4_DIR}/*.docx'), key=lambda f: int(re.search(r'Lesson\s*(\d+)', f).group(1)))
    for f in nce4_files:
        num = int(re.search(r'Lesson\s*(\d+)', f).group(1))
        docx_cache[('nce4', num)] = parse_docx_words(f)
    print(f'docx 笔记: NCE3 {len(nce3_files)} 课, NCE4 {len(nce4_files)} 课')

    nce2_notes = parse_nce2_note(NCE2_NOTE)
    print(f'NCE2 迷你笔记: {len(nce2_notes)} 组')

    # 用户 Lesson PDF
    pdf_dir = '/data/.default/nce-site/library'
    lesson_pdfs = {}
    pdf_by_unit = {}
    for f in glob.glob(f'{pdf_dir}/**/Lesson*.pdf', recursive=True):
        m = re.search(r'Lesson\s*(\d+)', os.path.basename(f))
        if not m: continue
        num = int(m.group(1))
        rel = os.path.relpath(f, pdf_dir)
        book_key = 'nce1'
        if 'nce2' in rel: book_key = 'nce2'
        elif 'nce3' in rel: book_key = 'nce3'
        elif 'nce4' in rel: book_key = 'nce4'
        # 所有册: Lesson N -> 单元 (N+1)//2 (2课=1单元)
        unit = (num + 1) // 2
        is_odd = (num % 2 == 1)   # 所有册: 奇数=课文课, 偶数=语法练习课
        parsed = parse_lesson_pdf(f)
        parsed['lesson_num'] = num
        parsed['is_text_lesson'] = is_odd
        if (book_key, unit) in lesson_pdfs:
            ex = lesson_pdfs[(book_key, unit)]
            seen = {w['w'] for w in ex['words']}
            for w in parsed['words']:
                if w['w'] not in seen:
                    ex['words'].append(w)
            ex['sentences'].extend(parsed['sentences'])
            ex['grammar'].extend(parsed['grammar'])
        else:
            lesson_pdfs[(book_key, unit)] = parsed
        pdf_by_unit.setdefault((book_key, unit), []).append(rel)
        print(f'  PDF Lesson{num} ({["语法练习","课文"][is_odd]}) -> {book_key} 单元{unit}')

    # 加载 LiDuoMiao 结构化笔记
    notes = load_notes()
    print(f'结构化笔记: {len(notes)} 条')

    result = {}
    for key, label, prefix, count, level in BOOKS:
        units = []
        for i in range(1, count + 1):
            # 所有册统一: 单元 i = 奇数课(2i-1)课文 + 偶数课(2i)单词语法
            text_lesson = 2 * i - 1   # 奇数课: 课文
            # NCE1 LRC 文件按单元编号 (NCE1-001.lrc = 单元1 = 课1+2); 其他册按课编号
            lrc_idx = i if key == 'nce1' else text_lesson
            file = os.path.join(LRC_DIR, f'{prefix}-{lrc_idx:03d}.lrc')
            if not os.path.exists(file): continue
            meta, lines = parse_lrc(open(file, encoding='utf-8').read())
            title = re.sub(r'^\d+[&.]?\d*\.?\s*', '', meta.get('ti', '')).strip()
            if not title: title = f'Lesson {text_lesson}'
            en_lines = [l['en'] for l in lines if l['en']]
            zh_lines = [l['zh'] for l in lines if l['zh']]

            if key == 'nce1':
                note = notes.get((key, i))           # NCE1 notes 已是单元粒度
            else:
                note = merge_notes(notes.get((key, text_lesson)), notes.get((key, 2*i)))  # 两课合并
            pdf = lesson_pdfs.get((key, i), None)

            # ===== 词汇: notes 精选词优先, 课文提取补充, ECDICT 补音标 =====
            vocab = []
            seen = set()
            # 1. notes vocabulary (最权威)
            if note:
                for v in note_vocab_to_list(note):
                    info = ecd.get(v['w']) or {}
                    merged = {'w': v['w'], 'ipa': v['ipa'] or info.get('ipa',''),
                              'pos': v['pos'] or info.get('pos',''),
                              'def': v['def'] or info.get('def',''),
                              'freq': 1, 'collins': info.get('collins',0),
                              'exchange': info.get('exchange',''), 'note': v['note']}
                    vocab.append(merged); seen.add(v['w'])
            # 2. 课文提取补充 (去掉指令行与停用词)
            if len(vocab) < 12:
                order, counts = extract_vocab(en_lines)
                for w in order:
                    if w in seen: continue
                    info = ecd.get(w) or {}
                    vocab.append({'w': w, 'ipa': info.get('ipa',''), 'pos': info.get('pos',''),
                                  'def': info.get('def',''), 'freq': counts.get(w, 1),
                                  'collins': info.get('collins',0), 'exchange': info.get('exchange','')})
                    seen.add(w)
                    if len(vocab) >= 25: break
            # 3. PDF 词汇补充 (用户上传详细讲义)
            if pdf and pdf['words']:
                for w in pdf['words']:
                    if w['w'] in seen: continue
                    info = ecd.get(w['w']) or {}
                    vocab.append({'w': w['w'], 'ipa': w.get('ipa','') or info.get('ipa',''),
                                  'pos': w.get('pos','') or info.get('pos',''),
                                  'def': w.get('def','') or info.get('def',''),
                                  'freq': 1, 'collins': info.get('collins',0),
                                  'exchange': info.get('exchange',''), 'note': w.get('note','')})
                    seen.add(w['w'])
            # 4. docx 笔记补充 (NCE3/4, 课粒度: 合并奇数课+偶数课)
            if key in ('nce3', 'nce4'):
                docx_entry = merge_docx(docx_cache.get((key, text_lesson)), docx_cache.get((key, 2*i)))
            else:
                docx_entry = None
            if docx_entry and docx_entry['words']:
                for dw in docx_entry['words']:
                    if dw['w'] in seen: continue
                    info = ecd.get(dw['w']) or {}
                    vocab.append({'w': dw['w'], 'ipa': dw.get('ipa','') or info.get('ipa',''),
                                  'pos': dw.get('pos','') or info.get('pos',''),
                                  'def': dw.get('def','') or info.get('def',''),
                                  'freq': 1, 'collins': info.get('collins',0),
                                  'exchange': info.get('exchange',''), 'note': dw.get('note','')})
                    seen.add(dw['w'])
            vocab = vocab[:30]

            # ===== 语法: notes 结构化优先 =====
            grammar = []
            if note and note.get('grammar'):
                # 结构化语法: {title, definition, structure, usage, examples}
                for g in note['grammar'][:8]:
                    examples = g.get('examples', []) or []
                    ex_str = '\n'.join([f"{e.get('en','')} {e.get('zh','')}" for e in examples[:3]])
                    parts = []
                    if g.get('definition'): parts.append(f"定义：{g['definition']}")
                    if g.get('structure'): parts.append(f"结构：{g['structure']}")
                    if g.get('usage'): parts.append(f"用法：{g['usage']}")
                    if ex_str: parts.append(f"例句：\n{ex_str}")
                    grammar.append({'title': g.get('title', '语法点'),
                                    'body': '\n'.join(parts)})
            elif pdf and pdf['grammar']:
                grammar = [{'title': g[:40], 'body': g} for g in pdf['grammar'][:8]]
            elif key == 'nce1' and i in NCE1_GRAMMAR:
                grammar = [{'title': g, 'body': ''} for g in NCE1_GRAMMAR[i]]
            elif key == 'nce2':
                pair = f"{i*2-1}-{i*2}"
                if pair in nce2_notes:
                    grammar = [{'title': g[:40], 'body': g} for g in nce2_notes[pair][:8]]
            if not grammar and docx_entry and docx_entry['grammar']:
                grammar = [{'title': g[:40], 'body': g} for g in docx_entry['grammar'][:8]]

            # ===== 词组 (notes phrases) =====
            phrases = []
            if note and note.get('phrases'):
                for p in note['phrases'][:10]:
                    exs = p.get('examples', []) or []
                    phrases.append({
                        'phrase': p.get('phrase', ''),
                        'usage': p.get('usage', ''),
                        'examples': [{'en': e.get('en',''), 'zh': e.get('zh','')} for e in exs[:3]]
                    })

            # ===== 句型 (notes sentencePatterns) =====
            patterns = []
            if note and note.get('sentencePatterns'):
                for sp in note['sentencePatterns'][:6]:
                    ims = sp.get('imitations', []) or []
                    patterns.append({
                        'pattern': sp.get('pattern', ''),
                        'original': sp.get('original', {}).get('en', '') if isinstance(sp.get('original'), dict) else '',
                        'imitations': [{'en': x.get('en',''), 'zh': x.get('zh','')} for x in ims[:3]]
                    })

            # ===== 训练题 =====
            quizzes = gen_quiz(title, en_lines, zh_lines, vocab, ecd, level)
            if pdf:
                for s in pdf['sentences'][:3]:
                    if len(quizzes) >= 10: break
                    quizzes.append({'type': 'trans', 'q': s, 'opts': [], 'answer': '见课文',
                                    'explain': s})

            units.append({
                'id': i, 'title': title,
                'subtitle': meta.get('al', ''),
                'lines': lines,
                'audio': f'{AUDIO_BASE}/{prefix}-{lrc_idx:03d}.mp3',
                'vocab': vocab,
                'grammar': grammar,
                'phrases': phrases,
                'patterns': patterns,
                'quizzes': quizzes,
                'lesson_nums': [text_lesson, 2*i],
                'has_detail': bool(pdf),
                'pdfs': [{'file': 'library/' + p, 'name': os.path.basename(p)} for p in pdf_by_unit.get((key, i), [])],
            })
        result[key] = {'label': label, 'units': units}
        total_v = sum(len(u['vocab']) for u in units)
        total_g = sum(len(u['grammar']) for u in units)
        total_q = sum(len(u['quizzes']) for u in units)
        total_p = sum(len(u['phrases']) for u in units)
        with_ipa = sum(1 for u in units for v in u['vocab'] if v.get('ipa'))
        total_w = sum(len(u['vocab']) for u in units)
        print(f'{key}: {len(units)} 单元, 词汇 {total_v} (音标率 {with_ipa*100//max(total_w,1)}%), 语法 {total_g}, 词组 {total_p}, 训练 {total_q}')

    # ===== 输出 =====
    os.makedirs(OUT_DIR, exist_ok=True)
    index = {}
    for key, label, prefix, count, level in BOOKS:
        units = result[key]['units']
        units_dir = os.path.join(OUT_DIR, 'units', key)
        os.makedirs(units_dir, exist_ok=True)
        for u in units:
            with open(os.path.join(units_dir, f'{u["id"]:03d}.json'), 'w', encoding='utf-8') as f:
                json.dump(u, f, ensure_ascii=False)
        index[key] = {
            'label': label,
            'units': [{
                'id': u['id'],
                'title': u['title'],
                'lesson_nums': u['lesson_nums'],
                'has_detail': u['has_detail'],
                'vocab_count': len(u['vocab']),
                'grammar_count': len(u['grammar']),
                'quiz_count': len(u['quizzes']),
                'keywords': [v['w'] for v in u['vocab'][:25]],
            } for u in units]
        }
    with open(os.path.join(OUT_DIR, 'index.json'), 'w', encoding='utf-8') as f:
        json.dump(index, f, ensure_ascii=False)
    print(f'写入索引 ({os.path.getsize(os.path.join(OUT_DIR,"index.json"))/1024:.0f}KB)')

    lib_index = []
    for f in glob.glob('/data/.default/nce-site/library/**/*.pdf', recursive=True):
        rel = os.path.relpath(f, '/data/.default/nce-site/library')
        m = re.search(r'Lesson\s*(\d+)', os.path.basename(f))
        num = int(m.group(1)) if m else 0
        book = 'nce1'
        if 'nce2' in rel: book = 'nce2'
        elif 'nce3' in rel: book = 'nce3'
        elif 'nce4' in rel: book = 'nce4'
        lib_index.append({
            'file': 'library/' + rel,
            'name': os.path.basename(f),
            'lesson': num,
            'book': book,
            'size': os.path.getsize(f),
        })
    lib_index.sort(key=lambda x: (x['book'], x['lesson']))
    with open(os.path.join(OUT_DIR, 'library.json'), 'w', encoding='utf-8') as f:
        json.dump(lib_index, f, ensure_ascii=False)
    print(f'资料库索引: {len(lib_index)} 个 PDF')

    ecd.close()

if __name__ == '__main__':
    main()
