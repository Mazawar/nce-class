#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
NCE 学习站 v2 数据构建器 (v3 重构版)
数据源 (优先级从高到低):
  1. LiDuoMiao notes 结构化笔记 (每课精选词汇+词组+语法+句型)  data/notes/{NCE1,NCE2,NCE3,NCE4}/*.json
  2. hibenba 夸克英语笔记 PDF (仅作可查看资源, 不解析内容)     data/notes-pdf/{nce1,nce2,nce3,nce4}/Lesson*.pdf -> 部署为 /pdf/
  3. LRC 课文 (英中对照+时间轴+音频)                          data/lrc/*.lrc
  4. ECDICT 词典 (音标补充)                                   data/stardict.db
输出: /data/.default/nce-site/public/data/ (index.json + units/{nce1,nce2,nce3,nce4}/*.json + library.json)
"""
import os, re, json, glob, sys, random, sqlite3

LRC_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'data', 'lrc')
AUDIO_BASE = 'audio'
ECDB = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'data', 'stardict.db')
NOTES_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'data', 'notes')
OUT_DIR = '/data/.default/nce-site/public/data'
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from nce1_grammar import NCE1_GRAMMAR

BOOKS = [
    # 第一册: 72 单元 (2课=1单元); 二三四册: 每课一单元 (课粒度, 笔记逐课对应)
    ('nce1', '新概念英语第一册', 'NCE1', 72, 1),
    ('nce2', '新概念英语第二册', 'NCE2', 96, 2),
    ('nce3', '新概念英语第三册', 'NCE3', 60, 3),
    ('nce4', '新概念英语第四册', 'NCE4', 48, 4),
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
                if lesson is None or lesson < 1 or lesson > count: continue
                notes[(book_key, lesson)] = data
    return notes


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

    # 扫描 hibenba 夸克英语笔记 PDF（notes-pdf, 仅作资源索引, 不解析内容）
    NOTES_PDF_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'data', 'notes-pdf')
    pdf_index = {}   # (book_key, lesson) -> [{'name','file','size'}]
    for bk_dir, book_key in [('nce1', 'nce1'), ('nce2', 'nce2'), ('nce3', 'nce3'), ('nce4', 'nce4')]:
        d = os.path.join(NOTES_PDF_DIR, bk_dir)
        if not os.path.isdir(d): continue
        for f in sorted(glob.glob(os.path.join(d, 'Lesson*.pdf'))):
            m = re.search(r'Lesson\s*(\d+)', os.path.basename(f))
            if not m: continue
            num = int(m.group(1))
            pdf_index.setdefault((book_key, num), []).append({
                'name': os.path.basename(f),
                'file': f'pdf/{bk_dir}/{os.path.basename(f)}',
                'size': os.path.getsize(f),
            })
    print(f'夸克笔记 PDF 资源: {sum(len(v) for v in pdf_index.values())} 个')

    # 加载 LiDuoMiao 结构化笔记
    notes = load_notes()
    print(f'结构化笔记: {len(notes)} 条')

    result = {}
    for key, label, prefix, count, level in BOOKS:
        units = []
        for i in range(1, count + 1):
            if key == 'nce1':
                # 第一册: 单元 i = 奇数课(2i-1)课文 + 偶数课(2i)单词语法; LRC 按单元编号
                text_lesson = 2 * i - 1
                lrc_idx = i
                note = notes.get((key, i))            # 单元粒度
            else:
                # 二三四册: 每课一单元 (课粒度); LRC 按课编号
                text_lesson = i
                lrc_idx = i
                note = notes.get((key, i))            # 课粒度
            file = os.path.join(LRC_DIR, f'{prefix}-{lrc_idx:03d}.lrc')
            if not os.path.exists(file): continue
            meta, lines = parse_lrc(open(file, encoding='utf-8').read())
            title = re.sub(r'^\d+[&.]?\d*\.?\s*', '', meta.get('ti', '')).strip()
            if not title: title = f'Lesson {text_lesson}'
            en_lines = [l['en'] for l in lines if l['en']]
            zh_lines = [l['zh'] for l in lines if l['zh']]

            # 夸克笔记 PDF 资源: nce1 关联奇数课+偶数课; 二三四册关联该课
            if key == 'nce1':
                pdf = []
                for ln in (text_lesson, 2 * i):
                    pdf += pdf_index.get((key, ln), [])
            else:
                pdf = pdf_index.get((key, i), [])

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
            # 3. (PDF 仅作资源, 不解析补充词汇)
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
            elif key == 'nce1' and i in NCE1_GRAMMAR:
                grammar = [{'title': g, 'body': ''} for g in NCE1_GRAMMAR[i]]

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
                'lesson_nums': [text_lesson, 2*i] if key == 'nce1' else [text_lesson],
                'has_detail': bool(pdf),
                'pdfs': pdf,
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
    for (bk, ln), items in sorted(pdf_index.items()):
        for it in items:
            lib_index.append({'book': bk, 'lesson': ln, 'name': it['name'], 'file': it['file'], 'size': it['size']})
    with open(os.path.join(OUT_DIR, 'library.json'), 'w', encoding='utf-8') as f:
        json.dump(lib_index, f, ensure_ascii=False)
    print(f'资料库索引: {len(lib_index)} 个 PDF')

    ecd.close()

if __name__ == '__main__':
    main()
