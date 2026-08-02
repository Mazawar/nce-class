# NCE 学习站数据来源清单

> 本文件记录 `data/` 目录下所有数据的来源，防止下次同步/重下找不到。
> 最后更新: 2026-08-02 (notes-pdf 改为资源索引)

## 目录结构

```
data/
├── lrc/          # 四册课文 LRC（英中对照+时间轴）  276 个
├── audio/        # 四册音频 MP3                     276 个
├── notes/        # LiDuoMiao 结构化笔记（主数据源）  276 个
│   ├── NCE1/     #   72 个 (001-002.json = 单元1, 2课=1单元, 单元粒度)
│   ├── NCE2/     #   96 个 (01.json = 第1课, 课粒度)
│   ├── NCE3/     #   60 个 (01.json = 第1课, 课粒度)
│   └── NCE4/     #   48 个 (01.json = 第1课, 课粒度)
├── notes-pdf/    # hibenba 夸克英语笔记 PDF（仅作可查看资源，不解析内容）258 个
│   ├── nce1/     #   73 个 (Lesson000 + 奇数课 1~143; 偶数课为练习课源仓库没有)
│   ├── nce2/     #   97 个 (Lesson000 + 1~96 全)
│   ├── nce3/     #   61 个 (Lesson000 + 1~60 全)
│   └── nce4/     #   27 个 (Lesson000 + 1~27, 缺 L21 源仓库没有)
├── NCE1-book.json / NCE2-book.json / NCE3-book.json  # 册元数据（旧，仅 dl_audio 用）
└── stardict.db   # ECDICT 词典（812MB，音标/释义/柯林斯星级补充）
```

> 注: 原 data/NCE2（迷你笔记）、data/NCE3、data/NCE4（docx 笔记）已于 2026-08-02 删除；
> library/（用户上传 Lesson PDF）已删除，由 hibenba notes-pdf 替代（仅作资源）。

## 四册统一结构（2026-08-02 起）

**所有册都是 2 课=1 单元，奇数课=课文、偶数课=单词语法：**

| 册 | 课数 | 单元数 | LRC/音频文件 | notes 粒度 |
|----|------|--------|--------------|-----------|
| NCE1 | 144 | 72 | NCE1-{单元}.lrc（单元粒度） | 001-002.json（单元粒度）|
| NCE2 | 96 | 48 | NCE2-{课}.lrc（课粒度，取奇数课） | 01.json（课粒度，两课合并）|
| NCE3 | 60 | 30 | NCE3-{课}.lrc（课粒度，取奇数课） | 01.json（课粒度，两课合并）|
| NCE4 | 48 | 24 | NCE4-{课}.lrc（课粒度，取奇数课） | 01.json（课粒度，两课合并）|

- 单元 i = 课 (2i-1)（课文）+ 课 (2i)（单词语法）
- 课文/音频用奇数课文件；词汇/语法/词组/句型为两课 notes 合并
- 左侧栏显示 `L1·2`；标题 "Lesson 1 & 2 · A Private Conversation"
- PDF 挂载: Lesson N → 单元 (N+1)//2（所有册一致）

## 数据源

### 1. 课文 LRC + 音频（主：nce.mleo.site）
- **URL**: `https://nce.mleo.site/{NCE1|NCE2|NCE3|NCE4}/book.json`（返回册元数据）
- **LRC**: `https://nce.mleo.site/{BOOK}/{filename}.lrc`
- **MP3**: `https://nce.mleo.site/{BOOK}/{filename}.mp3`
- **需要代理**: `--proxy http://127.0.0.1:7890`
- **下载脚本**: `scripts/dl_nce4.py`（NCE4 补齐用，可改 BOOKS 复用）
- 每册数量: NCE1=72, NCE2=96, NCE3=60, NCE4=48

### 2. 结构化笔记（主数据源：LiDuoMiao/new-concept-english）
- **GitHub**: `https://github.com/LiDuoMiao/new-concept-english`
- 字段: vocabulary(音标/词性/释义/用法), phrases(词组+例句), grammar(结构化:标题/定义/结构/用法/例句), sentencePatterns(句型+仿写)
- NCE1 文件名 `001-002.json` = 2 课 1 单元；NCE2/3/4 文件名 `01.json` = 单课
- 下载方式: `git clone https://github.com/LiDuoMiao/new-concept-english` 或 Release zip（需代理）

### 3. ECDICT 词典（音标/释义补充）
- **GitHub**: `https://github.com/skywind3000/ECDICT`
- Release 有 sqlite 版（340 万词条，含 phonetic/translation/collins/exchange）
- 本项目用的是 sqlite 版，拷贝为 `stardict.db`
- 注意: Release assets 没有 csv，只有 sqlite/其他格式

### 4. hibenba 夸克英语笔记 PDF（资源：可查看/下载，不解析内容）
- **GitHub**: `https://github.com/hibenba/New-Concept-English`
- 每课 PDF 含单词+音标+词性+释义+文法；本项目仅作为"本课资料/资料库"可查看资源
- 下载脚本: `scripts/dl_notes_pdf.py`（批量下载 258 个，需代理）
- 构建时扫描生成索引（library.json + 单元 pdfs 字段），`file` 字段 = `pdf/{nce1..4}/LessonXXX.pdf`
- 部署: `sudo rsync -a data/notes-pdf/ /opt/1panel/www/sites/nce/index/pdf/`

## 重建命令

```bash
cd /data/.default/nce-site
python3 scripts/build-data.py   # 生成 public/data/（index.json + units/ + library.json）
npm run build                   # vite 打包 dist
sudo rsync -a dist/ /opt/1panel/www/sites/nce/index/ --delete --exclude audio/ --exclude pdf/
sudo rsync -a data/audio/ /opt/1panel/www/sites/nce/index/audio/      # 617MB，增量同步
sudo rsync -a data/notes-pdf/ /opt/1panel/www/sites/nce/index/pdf/    # 334MB，增量同步
```

> ⚠️ 部署 `dist/` 时务必 `--exclude audio/ --exclude pdf/`，否则会把单独部署的音频/PDF 删掉。

## 构建脚本职责

`scripts/build-data.py` 读取 data/ → 输出 `public/data/index.json` + `units/{nce1,nce2,nce3,nce4}/*.json`：
- 词汇: notes 精选词优先 → 课文提取补充 → PDF 补充 → docx 补充，ECDICT 补音标
- 语法: notes 结构化优先 → PDF → NCE1 标准语法表 → NCE2 迷你笔记 → docx
- 词组/句型: notes phrases/sentencePatterns
- 训练题: gen_quiz 基于课文+词汇自动生成（8 题/课）
