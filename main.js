import './style.css';

// ====== STATE ======
const INDEX_URL = './data/index.json';
const LIB_URL = './data/library.json';
let NCE = null;          // 索引（轻量）
let LIB = [];
let currentBook = 'nce1';
let currentUnit = 1;
let currentTab = 'text';
let showZh = true;
let currentLine = -1;
let audio = null;
let quizState = null;
const unitCache = {};    // 按需加载的单元数据缓存 { 'nce1-1': {...} }

// ====== DOM ======
const bookSwitch = document.getElementById('book-switch');
const unitList = document.getElementById('unit-list');
const content = document.getElementById('content');
const headLesson = document.getElementById('head-lesson');
const headTitle = document.getElementById('head-title');
const btnPlay = document.getElementById('btn-play');
const searchInput = document.getElementById('search-input');
const tabs = document.getElementById('tabs');
const audioEl = document.getElementById('audio-player');

// ====== LOAD ======
async function init() {
  try {
    const [res, resLib] = await Promise.all([
      fetch(INDEX_URL),
      fetch(LIB_URL).catch(() => null),
    ]);
    NCE = await res.json();
    if (resLib) LIB = await resLib.json();
    audio = audioEl;
    renderBookSwitch();
    renderUnitList();
    updateLibBadge();
    const saved = loadProgress();
    currentBook = saved.book;
    currentUnit = saved.unit;
    renderBookSwitch();
    renderUnitList();
    // hash 路由: #/book/unit/tab
    const hm = /^#\/(nce[1-4])\/(\d+)(?:\/(\w+))?/.exec(location.hash);
    if (hm) {
      if (NCE[hm[1]]) currentBook = hm[1];
      currentUnit = parseInt(hm[2], 10) || 1;
      const tab = ['text', 'words', 'grammar', 'quiz'].includes(hm[3]) ? hm[3] : 'text';
      selectUnit(currentUnit, tab);
    } else {
      selectUnit(currentUnit);
    }
  } catch (e) {
    content.innerHTML = `<div class="empty-state"><div class="empty-orb">⚠️</div><div class="empty-title">数据加载失败</div><div class="empty-sub">${e.message}</div></div>`;
  }
}

// ====== 按需加载单元数据 ======
async function loadUnit(book, id) {
  const key = `${book}-${id}`;
  if (unitCache[key]) return unitCache[key];
  const res = await fetch(`./data/units/${book}/${String(id).padStart(3, '0')}.json`);
  if (!res.ok) throw new Error(`单元 ${id} 加载失败 (${res.status})`);
  const data = await res.json();
  unitCache[key] = data;
  return data;
}

// ====== PROGRESS ======
function loadProgress() {
  try { return JSON.parse(localStorage.getItem('nce_progress')) || { book: 'nce1', unit: 1 }; }
  catch (e) { return { book: 'nce1', unit: 1 }; }
}
function saveProgress() {
  localStorage.setItem('nce_progress', JSON.stringify({ book: currentBook, unit: currentUnit }));
}
function loadDone() {
  try { return JSON.parse(localStorage.getItem('nce_done')) || {}; }
  catch (e) { return {}; }
}
function saveDone(d) {
  localStorage.setItem('nce_done', JSON.stringify(d));
}

// ====== RENDER: BOOK SWITCH ======
function renderBookSwitch() {
  bookSwitch.innerHTML = '';
  for (const [key, book] of Object.entries(NCE)) {
    const btn = document.createElement('button');
    btn.className = 'book-tab' + (key === currentBook ? ' active' : '');
    btn.textContent = book.label.replace('新概念英语', '');
    btn.onclick = () => { currentBook = key; currentUnit = 1; renderBookSwitch(); renderUnitList(); selectUnit(1); };
    bookSwitch.appendChild(btn);
  }
}

// ====== RENDER: UNIT LIST ======
function renderUnitList(filter) {
  const units = NCE[currentBook].units;
  unitList.innerHTML = '';
  const q = (filter || searchInput.value || '').trim().toLowerCase();
  let shown = 0;
  units.forEach((u, idx) => {
    const kw = (u.keywords || []).filter(w => w && w.includes(q));
    const match = !q || u.title.toLowerCase().includes(q) || String(u.id).includes(q) ||
      (u.lesson_nums || []).some(n => String(n).includes(q)) || kw.length > 0;
    if (q && !match) return;
    shown++;
    const item = document.createElement('div');
    item.className = 'lesson-item' + (u.id === currentUnit ? ' active' : '');
    const nums = u.lesson_nums ? u.lesson_nums.join('·') : u.id;
    let titleHtml = `<span class="lesson-title">${escHtml(u.title)}</span>`;
    if (q && kw.length && !u.title.toLowerCase().includes(q) && !String(u.id).includes(q)) {
      titleHtml = `<span class="lesson-title">${escHtml(u.title)}</span><span class="kw-hit">${kw.slice(0, 2).map(escHtml).join('、')}</span>`;
    }
    item.innerHTML = `<span class="lesson-num">L${nums}</span>${titleHtml}` +
      (u.has_detail ? `<span class="lesson-dot"></span>` : '');
    item.style.animationDelay = `${Math.min(idx * 18, 400)}ms`;
    item.onclick = () => selectUnit(u.id);
    unitList.appendChild(item);
  });
  if (!shown) {
    unitList.innerHTML = `<div class="lib-empty" style="padding:30px 0">没有匹配「${escHtml(q)}」的课程</div>`;
  }
  updateFooterStats();
}

// ====== SELECT UNIT ======
async function selectUnit(id, tab) {
  currentUnit = id;
  saveProgress();
  stopPlayback();
  renderUnitList();
  if (searchInput.value.trim() && !NCE[currentBook].units.find(u => u.id === id)) {
    searchInput.value = '';
    renderUnitList();
  }
  currentTab = tab || 'text';
  setTabActive(currentTab);
  try {
    if (location.hash !== `#/${currentBook}/${id}/${currentTab}`) {
      history.replaceState(null, '', `#/${currentBook}/${id}/${currentTab}`);
    }
  } catch (e) {}
  // 立即渲染头部信息（索引里有）
  const meta = NCE[currentBook].units.find(u => u.id === id);
  if (meta) {
    headLesson.textContent = `${NCE[currentBook].label} · 单元 ${id}`;
    headTitle.textContent = `Lesson ${meta.lesson_nums ? meta.lesson_nums.join(' & ') : id} · ${meta.title}`;
  }
  // 显示加载态
  content.innerHTML = `<div class="empty-state"><div class="empty-orb" style="animation:orbFloat 1.2s ease-in-out infinite">⏳</div><div class="empty-title">加载课程中…</div></div>`;
  try {
    const unit = await loadUnit(currentBook, id);
    audio.src = unit.audio;
    audio.load();
    updateTabCounts(meta);
    // 按当前 tab 渲染
    if (currentTab === 'words') renderWords(unit);
    else if (currentTab === 'grammar') renderGrammar(unit);
    else if (currentTab === 'quiz') renderQuiz(unit);
    else renderUnitContent(unit);
  } catch (e) {
    content.innerHTML = `<div class="empty-state"><div class="empty-orb">⚠️</div><div class="empty-title">加载失败</div><div class="empty-sub">${e.message}</div></div>`;
  }
}

// 本课资料胶囊 HTML (渲染到课文标题最右侧)
function headPdfChips(unit) {
  const pdfs = (unit && unit.pdfs) || [];
  if (!pdfs.length) return '';
  return pdfs.map(p => {
    const isOdd = /Lesson(\d+)/.exec(p.name);
    const type = isOdd && parseInt(isOdd[1], 10) % 2 === 1 ? '课文' : '练习';
    return `<span class="unit-pdf-chip head-pdf-chip" onclick="openPdf('${encodeURIComponent(p.file)}','${escHtmlAttr(p.name)}')" title="${escHtmlAttr(p.name)}">
      <span class="unit-pdf-icon">📄</span>
      <span class="unit-pdf-name">${escHtml(p.name.replace('.pdf', ''))}</span>
      <span class="unit-pdf-type">${type}</span>
    </span>`;
  }).join('');
}

function getUnit() {
  return unitCache[`${currentBook}-${currentUnit}`] || null;
}

// ====== RENDER: UNIT (课文视图) ======
function renderUnitContent(unit) {
  let html = `<div class="lesson-card">`;
  html += `<div class="lesson-header">
    <div class="lesson-head-left">
      <div class="lesson-head-title">${escHtml(unit.title)}</div>
      ${unit.subtitle ? `<div class="lesson-head-sub">${escHtml(unit.subtitle)}</div>` : ''}
    </div>
    <div class="lesson-head-pdfs">${headPdfChips(unit)}</div>
  </div>`;
  html += `<div class="lines">`;
  unit.lines.forEach((line, idx) => {
    if (!line.en && !line.zh) return;
    html += `<div class="line" id="line-${idx}" data-time="${line.time}" data-idx="${idx}" style="animation-delay:${Math.min(idx * 30, 600)}ms">
      <div class="line-en">${escHtml(line.en)}</div>
      ${showZh && line.zh ? `<div class="line-zh">${escHtml(line.zh)}</div>` : ''}
    </div>`;
  });
  html += `</div>`;
  html += `<div class="listen-bar">
    <button class="btn-play btn-play-listen" style="width:38px;height:38px;font-size:14px" onclick="togglePlay()">▶</button>
    <div class="listen-info" id="listen-info">点击任意句子跳转播放 · 空格播放/暂停</div>
  </div>`;
  html += `</div>`;
  content.innerHTML = html;
  updatePlayButtons();

  document.querySelectorAll('.line').forEach(el => {
    el.onclick = () => {
      const t = parseFloat(el.dataset.time) / 1000;
      if (audio && audio.src) { audio.currentTime = t; if (!audio.paused) audio.play(); }
      setCurrentLine(parseInt(el.dataset.idx, 10));
    };
  });
}

// ====== TAB ======
async function switchTab(tab) {
  if (!NCE) return;
  currentTab = tab;
  setTabActive(tab);
  try {
    if (location.hash !== `#/${currentBook}/${currentUnit}/${tab}`) {
      history.replaceState(null, '', `#/${currentBook}/${currentUnit}/${tab}`);
    }
  } catch (e) {}
  if (tab === 'library') { renderLibrary(); content.scrollTop = 0; return; }
  const unit = getUnit();
  if (!unit) {
    // 数据未加载（直接点 tab 时）
    await selectUnit(currentUnit);
    return;
  }
  if (tab === 'text') renderUnitContent(unit);
  else if (tab === 'words') renderWords(unit);
  else if (tab === 'grammar') renderGrammar(unit);
  else if (tab === 'quiz') renderQuiz(unit);
  content.scrollTop = 0;
}

function setTabActive(tab) {
  document.querySelectorAll('.tab').forEach(b => {
    b.classList.toggle('active', b.dataset.tab === tab);
  });
}

function updateTabCounts(meta) {
  const cw = document.getElementById('tab-count-words');
  const cg = document.getElementById('tab-count-grammar');
  const cq = document.getElementById('tab-count-quiz');
  if (cw) cw.textContent = meta ? meta.vocab_count : 0;
  if (cg) cg.textContent = meta ? meta.grammar_count : 0;
  if (cq) cq.textContent = meta ? meta.quiz_count : 0;
  updateLibBadge();
}

// ====== 单词视图 ======
function renderWords(unit) {
  const vocab = unit.vocab || [];
  if (!vocab.length) {
    content.innerHTML = `<div class="lib-empty"><div class="lib-empty-orb">🔤</div><div>本课暂无单词数据</div></div>`;
    return;
  }
  let html = `<div class="word-list">`;
  vocab.forEach((v, i) => {
    const hasNote = v.note && v.note.length > 3;
    const stars = v.collins ? '★'.repeat(Math.min(5, v.collins)) : '';
    html += `<div class="word-item" style="animation-delay:${Math.min(i * 20, 400)}ms">
      <div class="word-item-main">
        <div class="word-item-left">
          <span class="word-w">${escHtml(v.w)}</span>
          ${v.ipa ? `<span class="word-ipa">${escHtml(v.ipa)}</span>` : ''}
        </div>
        <div class="word-item-right">
          ${stars ? `<span class="word-stars" title="柯林斯星级">${stars}</span>` : ''}
          ${v.pos ? `<span class="word-pos">${escHtml(v.pos)}</span>` : ''}
          <span class="word-def">${escHtml(v.def || '')}</span>
          ${v.exchange ? `<span class="word-exchange" title="词形变化">${escHtml(v.exchange.replace(/[0-9]/g, '').replace(/[a-z]:/g, m => m[0] + '·'))}</span>` : ''}
        </div>
        ${hasNote ? `<span class="word-toggle" onclick="toggleWordNote(this)">详解 ▾</span>` : ''}
      </div>
      ${hasNote ? `<div class="word-note"><div class="word-note-inner">${escHtml(v.note)}</div></div>` : ''}
    </div>`;
  });
  html += `</div>`;
  content.innerHTML = html;
}

// 单词详解展开/收起: JS 精确控制 height 过渡(从实际高度开始),
// 避免 max-height 固定值导致的收起滞后/展开截断; 兼容所有浏览器
function toggleWordNote(toggleEl) {
  const item = toggleEl.parentElement.parentElement;
  const note = item.querySelector('.word-note');
  if (!note) return;
  const inner = note.querySelector('.word-note-inner');
  if (!inner) return;
  if (item.classList.contains('open')) {
    // 收起: 从当前实际高度过渡到 0 (全程跟随)
    note.style.height = inner.scrollHeight + 'px';
    void note.offsetHeight;                 // 强制 reflow, 确保过渡起点
    note.style.height = '0px';
    item.classList.remove('open');
  } else {
    // 展开: 0 -> 实际高度
    item.classList.add('open');
    note.style.height = '0px';
    void note.offsetHeight;
    note.style.height = inner.scrollHeight + 'px';
  }
}

// ====== 语法视图 ======
function renderGrammar(unit) {
  const grammar = unit.grammar || [];
  const phrases = unit.phrases || [];
  const patterns = unit.patterns || [];
  if (!grammar.length && !phrases.length && !patterns.length) {
    content.innerHTML = `<div class="lib-empty"><div class="lib-empty-orb">🧩</div><div>本课暂无语法点</div></div>`;
    return;
  }
  const icons = ['🧩', '💡', '📌', '🔑', '📐', '⭐', '✨', '🎯'];
  let html = '';

  // 语法点
  if (grammar.length) {
    html += `<div class="grammar-section-title">📐 语法要点</div><div class="grammar-list">`;
    grammar.forEach((g, i) => {
      const title = typeof g === 'string' ? g : (g.title || '语法点');
      const body = typeof g === 'string' ? '' : (g.body || '');
      const hasBody = body && body.length > 2;
      html += `<div class="grammar-item${hasBody ? ' has-body' : ''}" style="animation-delay:${Math.min(i * 25, 400)}ms">
        <span class="grammar-icon">${icons[i % icons.length]}</span>
        <div class="grammar-content">
          <div class="grammar-text">${formatGrammar(title)}</div>
          ${hasBody ? `<div class="grammar-body" style="display:none">${escHtml(body).replace(/\n/g, '<br>')}</div>
          <div class="grammar-expand" onclick="event.stopPropagation();const p=this.parentElement.querySelector('.grammar-body');const open=p.style.display!=='none';p.style.display=open?'none':'block';this.textContent=open?'详情 ▾':'收起 ▴'">详情 ▾</div>` : ''}
        </div>
      </div>`;
    });
    html += `</div>`;
  }

  // 词组短语
  if (phrases.length) {
    html += `<div class="grammar-section-title" style="margin-top:24px">🔗 重点词组</div><div class="phrase-list">`;
    phrases.forEach((p, i) => {
      html += `<div class="phrase-item" style="animation-delay:${Math.min(i * 20, 300)}ms">
        <div class="phrase-head">
          <span class="phrase-word">${escHtml(p.phrase)}</span>
          ${p.usage ? `<span class="phrase-usage">${escHtml(p.usage)}</span>` : ''}
        </div>
        ${p.examples && p.examples.length ? `<div class="phrase-examples">` +
          p.examples.map(e => `<div class="phrase-example"><span class="en">${escHtml(e.en)}</span>${e.zh ? `<span class="zh">${escHtml(e.zh)}</span>` : ''}</div>`).join('') +
          `</div>` : ''}
      </div>`;
    });
    html += `</div>`;
  }

  // 句型
  if (patterns.length) {
    html += `<div class="grammar-section-title" style="margin-top:24px">🧱 核心句型</div><div class="pattern-list">`;
    patterns.forEach((p, i) => {
      html += `<div class="pattern-item" style="animation-delay:${Math.min(i * 20, 300)}ms">
        <div class="pattern-head">
          <span class="pattern-main">${escHtml(p.pattern)}</span>
          ${p.original ? `<span class="pattern-orig">${escHtml(p.original)}</span>` : ''}
        </div>
        ${p.imitations && p.imitations.length ? `<div class="pattern-imits">` +
          p.imitations.map(x => `<div class="pattern-imit"><span class="en">${escHtml(x.en)}</span>${x.zh ? `<span class="zh">${escHtml(x.zh)}</span>` : ''}</div>`).join('') +
          `</div>` : ''}
      </div>`;
    });
    html += `</div>`;
  }
  content.innerHTML = html;
}

function formatGrammar(g) {
  return escHtml(g).replace(/([A-Za-z][A-Za-z'’\s\-]{2,})/g, '<span class="en">$1</span>');
}

// ====== 训练视图 ======
function renderQuiz(unit) {
  const quizzes = unit.quizzes || [];
  if (!quizzes.length) {
    content.innerHTML = `<div class="lib-empty"><div class="lib-empty-orb">✏️</div><div>本课暂无训练题</div></div>`;
    return;
  }
  quizState = { unit, quizzes, idx: 0, score: 0, answered: false, total: quizzes.length };
  content.innerHTML = `<div class="quiz-wrap" id="quiz-wrap"></div>`;
  renderQuizItem();
}

function renderQuizItem() {
  const s = quizState;
  const q = s.quizzes[s.idx];
  if (!q) return;
  const wrap = document.getElementById('quiz-wrap');
  const pct = Math.round((s.idx / s.total) * 100);
  let html = `<div class="quiz-progress">
    <div class="quiz-progress-bar"><div class="quiz-progress-fill" style="width:${pct}%"></div></div>
    <div class="quiz-progress-text">${s.idx + 1} / ${s.total}</div>
  </div>`;
  html += `<div class="quiz-card" id="quiz-card">`;
  const typeNames = { choice: '选择题', fill: '填空', trans: '翻译', listen: '听力' };
  html += `<span class="quiz-type ${q.type}">${typeNames[q.type] || q.type}</span>`;
  const isZh = q.type === 'trans';
  html += `<div class="quiz-q ${isZh ? 'zh-q' : ''}">${escHtml(q.q)}</div>`;
  if (q.type === 'choice') {
    html += `<div class="quiz-opts">`;
    q.opts.forEach((o, oi) => {
      html += `<button class="quiz-opt" data-opt="${String.fromCharCode(65 + oi)}" onclick="answerChoice(this,'${String.fromCharCode(65 + oi)}')">
        <span class="opt-letter">${String.fromCharCode(65 + oi)}</span><span>${escHtml(o)}</span>
      </button>`;
    });
    html += `</div>`;
  } else if (q.type === 'fill') {
    html += `<input class="quiz-input" id="quiz-input" placeholder="输入英文单词…" onkeydown="if(event.key==='Enter')answerFill()">`;
  } else if (q.type === 'trans') {
    html += `<textarea class="quiz-input" id="quiz-input" rows="3" placeholder="输入英文翻译…" style="resize:vertical"></textarea>`;
  }
  html += `<div class="quiz-explain" id="quiz-explain" style="display:none"></div>`;
  html += `<div class="quiz-actions">
    <button class="btn" id="quiz-prev" onclick="quizPrev()" ${s.idx === 0 ? 'disabled' : ''}>‹ 上一题</button>
    <div style="flex:1"></div>
    ${q.type === 'choice' ? '' : `<button class="btn btn-primary" id="quiz-submit" onclick="answerFill()">提交 ✓</button>`}
    <button class="btn btn-primary" id="quiz-next" onclick="quizNext()" style="display:none">下一题 ›</button>
    <button class="btn btn-primary" id="quiz-finish" onclick="quizFinish()" style="display:none">完成 ✓</button>
  </div>`;
  html += `</div>`;
  wrap.innerHTML = html;
  if (q.type !== 'choice') {
    const inp = document.getElementById('quiz-input');
    if (inp) inp.focus();
  }
}

function answerChoice(el, letter) {
  const s = quizState;
  if (!s || s.answered) return;
  const q = s.quizzes[s.idx];
  s.answered = true;
  const correct = q.answer === letter;
  if (correct) s.score++;
  document.querySelectorAll('.quiz-opt').forEach(o => {
    o.classList.add('disabled');
    if (o.dataset.opt === q.answer) o.classList.add('correct');
  });
  if (!correct) el.classList.add('wrong');
  showExplain(q);
  showNextBtn();
}

function answerFill() {
  const s = quizState;
  if (!s || s.answered) return;
  const q = s.quizzes[s.idx];
  const inp = document.getElementById('quiz-input');
  if (!inp) return;
  const val = inp.value.trim().toLowerCase();
  if (!val) return;
  s.answered = true;
  const correct = normalize(val) === normalize(q.answer);
  if (correct) s.score++;
  inp.style.borderColor = correct ? 'var(--ok)' : 'var(--danger)';
  showExplain(q, val);
  showNextBtn();
}

function normalize(s) {
  return String(s).toLowerCase().replace(/[^a-z0-9']/g, '').replace(/'s$/, 's');
}

function showExplain(q, userAns) {
  const el = document.getElementById('quiz-explain');
  if (!el) return;
  el.style.display = 'block';
  let txt = '';
  if (userAns !== undefined && q.type !== 'choice') {
    const ok = normalize(userAns) === normalize(q.answer);
    txt += `${ok ? '✅ 回答正确！' : '❌ 正确答案: '}${q.type === 'fill' ? escHtml(q.answer) : ''}\n`;
  }
  if (q.explain) txt += escHtml(q.explain);
  el.innerHTML = txt;
}

function showNextBtn() {
  const s = quizState;
  const isLast = s.idx >= s.total - 1;
  const next = document.getElementById('quiz-next');
  const fin = document.getElementById('quiz-finish');
  const sub = document.getElementById('quiz-submit');
  if (sub) sub.style.display = 'none';
  if (isLast) { if (fin) fin.style.display = 'inline-block'; }
  else { if (next) next.style.display = 'inline-block'; }
}

function quizNext() {
  if (quizState.idx < quizState.total - 1) {
    quizState.idx++;
    quizState.answered = false;
    renderQuizItem();
  }
}
function quizPrev() {
  if (quizState.idx > 0) {
    quizState.idx--;
    quizState.answered = false;
    renderQuizItem();
  }
}
function quizFinish() {
  const s = quizState;
  const pct = Math.round((s.score / s.total) * 100);
  const wrap = document.getElementById('quiz-wrap');
  const emoji = pct === 100 ? '🏆' : pct >= 80 ? '🌟' : pct >= 60 ? '👍' : '💪';
  wrap.innerHTML = `<div class="quiz-card quiz-done" style="padding:60px 40px">
    <div class="empty-orb" style="width:90px;height:90px;font-size:40px;margin:0 auto 20px">${emoji}</div>
    <div class="quiz-done-score">${s.score} / ${s.total}</div>
    <div class="quiz-done-text">正确率 ${pct}%</div>
    <div style="margin-top:24px">
      <button class="btn btn-primary" onclick="renderQuiz(quizState.unit)">再练一次 🔄</button>
      <button class="btn" onclick="switchTab('text')" style="margin-left:10px">回课文 📖</button>
    </div>
  </div>`;
  const done = loadDone();
  const key = `${currentBook}-${currentUnit}`;
  if (!done[key]) {
    done[key] = { score: s.score, total: s.total, pct, ts: Date.now() };
    saveDone(done);
    updateFooterStats();
    renderUnitList();
  }
}

// ====== 资料库 ======
function showLibrary() { switchTab('library'); }

function renderLibrary() {
  if (!LIB || !LIB.length) {
    content.innerHTML = `<div class="lib-empty">
      <div class="lib-empty-orb">📁</div>
      <div>资料库暂无 PDF<br><small style="color:var(--text-2)">上传的 Lesson PDF 会自动出现在这里</small></div>
    </div>`;
    return;
  }
  const dirMeta = {
    nce1: { name: '新概念英语第一册', emoji: '📘', books: ['nce1'] },
    nce2: { name: '新概念英语第二册', emoji: '📗', books: ['nce2'] },
    nce3: { name: '新概念英语第三册', emoji: '📕', books: ['nce3'] },
    nce4: { name: '新概念英语第四册', emoji: '📙', books: ['nce4'] },
  };
  let html = '';
  for (const dirKey of ['nce1', 'nce2', 'nce3', 'nce4']) {
    const meta = dirMeta[dirKey];
    const items = LIB.filter(i => meta.books.includes(i.book));
    if (!items.length) continue;
    // 默认收起: 只显示册目录, 点击展开该册 PDF
    html += `<div class="lib-dir">
      <div class="lib-dir-head" onclick="toggleLibDir(this)">
        <span class="lib-arrow">▸</span>
        <span class="lib-dir-emoji">${meta.emoji}</span>
        <span class="lib-dir-name">${meta.name}</span>
        <span class="lib-dir-count">${items.length} 份</span>
      </div>
      <div class="lib-grid">`;
    items.forEach((item, i) => {
      const size = item.size > 1024 * 1024 ? `${(item.size / 1024 / 1024).toFixed(1)}MB` : `${Math.max(1, Math.round(item.size / 1024))}KB`;
      const isOdd = item.lesson % 2 === 1;
      const type = isOdd ? '课文' : '练习';   // 所有册: 奇数=课文, 偶数=语法练习
      html += `<div class="lib-card" style="animation-delay:${Math.min(i * 40, 500)}ms" onclick="openPdf('${encodeURIComponent(item.file)}','${escHtmlAttr(item.name)}')">
        <div class="lib-icon">📄</div>
        <div class="lib-card-info">
          <div class="lib-name">${escHtml(item.name.replace('.pdf', ''))}</div>
          <div class="lib-meta">
            <span class="lib-badge">${type}</span>
            <span>Lesson ${item.lesson}</span>
            <span>${size}</span>
          </div>
        </div>
        <div class="lib-view">查看 →</div>
      </div>`;
    });
    html += `</div></div>`;
  }
  content.innerHTML = html;
}

// 资料库目录展开/收起 (默认收起, 点击册头切换)
function toggleLibDir(headEl) {
  headEl.parentElement.classList.toggle('open');
}

// ====== PDF 内嵌查看 ======
function openPdf(encodedFile, name) {
  const modal = document.getElementById('pdf-modal');
  const frame = document.getElementById('pdf-frame');
  const title = document.getElementById('pdf-modal-title');
  if (!modal || !frame) return;
  title.textContent = name || decodeURIComponent(encodedFile);
  frame.src = decodeURIComponent(encodedFile);
  modal.classList.add('show');
  document.body.style.overflow = 'hidden';
}

function closePdfViewer(e) {
  if (e && e.target && !e.target.closest('.pdf-modal-box')) return; // 点遮罩关闭
  const modal = document.getElementById('pdf-modal');
  const frame = document.getElementById('pdf-frame');
  if (!modal) return;
  modal.classList.remove('show');
  if (frame) frame.src = 'about:blank';
  document.body.style.overflow = '';
}

// Esc 关闭 PDF
document.addEventListener('keydown', e => {
  if (e.key === 'Escape') closePdfViewer();
});

// ====== PLAYBACK ======
function togglePlay() {
  if (!audio || !audio.src) return;
  if (audio.paused) {
    audio.play();
  } else {
    audio.pause();
  }
}

// 同步所有播放按钮状态（右上角 + 课文底部）
function updatePlayButtons() {
  const playing = audio && audio.src && !audio.paused;
  document.querySelectorAll('.btn-play').forEach(b => {
    b.classList.toggle('playing', !!playing);
    b.textContent = playing ? '⏸' : '▶';
  });
}

function stopPlayback() {
  if (audio) { audio.pause(); audio.currentTime = 0; }
  updatePlayButtons();
  setCurrentLine(-1);
}

function setCurrentLine(idx) {
  currentLine = idx;
  document.querySelectorAll('.line').forEach(el => {
    el.classList.toggle('active', parseInt(el.dataset.idx, 10) === idx);
  });
  const info = document.getElementById('listen-info');
  if (info && idx >= 0) {
    const unit = getUnit();
    if (unit && unit.lines[idx]) {
      info.innerHTML = `<b>${escHtml(unit.lines[idx].en)}</b>`;
    }
  } else if (info) {
    info.textContent = '点击任意句子跳转播放 · 空格播放/暂停';
  }
}

function onTimeUpdate() {
  if (!audio || !audio.duration) return;
  const t = audio.currentTime * 1000;
  const unit = getUnit();
  if (!unit) return;
  let idx = -1;
  for (let i = 0; i < unit.lines.length; i++) {
    if (t >= unit.lines[i].time - 200) idx = i;
    else break;
  }
  if (idx !== currentLine) {
    setCurrentLine(idx);
    if (idx >= 0) {
      const el = document.getElementById('line-' + idx);
      if (el) {
        const r = el.getBoundingClientRect();
        if (r.top < 140 || r.bottom > window.innerHeight - 60) {
          el.scrollIntoView({ behavior: 'smooth', block: 'center' });
        }
      }
    }
  }
}
audioEl.addEventListener('timeupdate', onTimeUpdate);
audioEl.addEventListener('play', updatePlayButtons);
audioEl.addEventListener('pause', updatePlayButtons);
audioEl.addEventListener('ended', () => {
  updatePlayButtons();
  setCurrentLine(-1);
});

// ====== TOGGLE ZH ======
function toggleZhMode() {
  showZh = !showZh;
  const btn = document.getElementById('btn-zh');
  btn.classList.toggle('active', showZh);
  if (currentTab === 'text') {
    const unit = getUnit();
    if (unit) renderUnitContent(unit);
  }
}

// ====== NAV ======
function prevUnit() {
  const units = NCE[currentBook].units;
  const idx = units.findIndex(u => u.id === currentUnit);
  if (idx > 0) selectUnit(units[idx - 1].id);
}
function nextUnit() {
  const units = NCE[currentBook].units;
  const idx = units.findIndex(u => u.id === currentUnit);
  if (idx < units.length - 1) selectUnit(units[idx + 1].id);
}

// ====== SEARCH ======
searchInput.addEventListener('input', () => renderUnitList());

// ====== 移动端侧栏 ======
function toggleSidebar() {
  const sb = document.getElementById('sidebar');
  const mask = document.getElementById('sidebar-mask');
  const btn = document.getElementById('menu-btn');
  const isOpen = sb.classList.contains('open');
  sb.classList.toggle('open', !isOpen);
  mask.classList.toggle('show', !isOpen);
  btn.classList.toggle('open', !isOpen);
  document.body.style.overflow = isOpen ? '' : 'hidden';
}

// 移动端选择课程后自动关闭侧栏
document.addEventListener('click', e => {
  if (e.target.closest('.lesson-item') || e.target.closest('.book-tab')) {
    if (window.innerWidth <= 768) {
      const sb = document.getElementById('sidebar');
      if (sb && sb.classList.contains('open')) toggleSidebar();
    }
  }
});

// ====== HELPERS ======
function escHtml(s) {
  const d = document.createElement('div');
  d.textContent = s == null ? '' : String(s);
  return d.innerHTML;
}

function escHtmlAttr(s) {
  return escHtml(s).replace(/"/g, '&quot;');
}

function updateLibBadge() {
  const b = document.getElementById('lib-badge');
  if (b) b.textContent = (LIB || []).length;
  const c = document.getElementById('tab-count-lib');
  if (c) c.textContent = (LIB || []).length;
}

function updateFooterStats() {
  const el = document.getElementById('footer-stats');
  if (!el || !NCE) return;
  const units = NCE[currentBook].units;
  const done = loadDone();
  const cnt = units.filter(u => done[`${currentBook}-${u.id}`]).length;
  el.textContent = `${currentBook.toUpperCase()} 已完成 ${cnt}/${units.length}`;
  const bar = document.getElementById('progress-bar-mini');
  if (bar) bar.style.width = `${Math.round((cnt / units.length) * 100)}%`;
}

// keyboard
document.addEventListener('keydown', e => {
  const tag = (e.target.tagName || '').toLowerCase();
  if (tag === 'input' || tag === 'textarea') return;
  if (e.code === 'Space') { e.preventDefault(); togglePlay(); }
  else if (e.key === 'ArrowLeft') prevUnit();
  else if (e.key === 'ArrowRight') nextUnit();
  else if (e.key === '1') switchTab('text');
  else if (e.key === '2') switchTab('words');
  else if (e.key === '3') switchTab('grammar');
  else if (e.key === '4') switchTab('quiz');
});

// expose for inline onclick
window.switchTab = switchTab;
window.togglePlay = togglePlay;
window.prevUnit = prevUnit;
window.nextUnit = nextUnit;
window.toggleZhMode = toggleZhMode;
window.showLibrary = showLibrary;
window.renderQuiz = renderQuiz;
window.answerChoice = answerChoice;
window.toggleWordNote = toggleWordNote;
window.toggleLibDir = toggleLibDir;
window.answerFill = answerFill;
window.quizNext = quizNext;
window.quizPrev = quizPrev;
window.quizFinish = quizFinish;
window.openLib = openPdf;
window.openPdf = openPdf;
window.closePdfViewer = closePdfViewer;
window.toggleSidebar = toggleSidebar;

init();
