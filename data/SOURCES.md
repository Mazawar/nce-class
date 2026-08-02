# NCE 学习站数据来源清单

> 本文件记录 `data/` 目录下所有数据的来源，防止下次同步/重下找不到。
> 最后更新: 2026-08-02 (四册统一 2课=1单元)

## 目录结构

```
data/
├── lrc/          # 四册课文 LRC（英中对照+时间轴）  228 个
├── audio/        # 四册音频 MP3                     228 个
├── notes/        # LiDuoMiao 结构化笔记（主数据源）  276 个
│   ├── NCE1/     #   72 个 (001-002.json = 单元1, 2课=1单元, 单元粒度)
│   ├── NCE2/     #   96 个 (01.json = 第1课, 课粒度)
│   ├── NCE3/     #   60 个 (01.json = 第1课, 课粒度)
│   └── NCE4/     #   48 个 (01.json = 第1课, 课粒度)
├── NCE2/         # 新概念2迷你笔记.txt（兜底语法源）
├── NCE3/         # 新概念3册完整笔记 docx（60 课，详解补充）
├── NCE4/         # 新概念4册完整笔记 docx（32 课，详解补充）
├── NCE1-book.json / NCE2-book.json / NCE3-book.json  # 册元数据（旧，仅 dl_audio 用）
└── stardict.db   # ECDICT 词典（812MB，音标/释义/柯林斯星级补充）
```

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

### 4. docx 笔记（详解补充：NCE3/NCE4）
- 用户上传的《新概念3/4册完整笔记》docx
- NCE3 全 60 课，NCE4 仅 32 课（用户只上传了 32 课）
- 提供词根词缀/近义词/真题详解，作为词汇 note 字段

### 5. 用户上传 Lesson PDF（详细讲义）
- 存放: `library/nce1/`（如 Lesson001.pdf ~ Lesson039.pdf）
- 构建时自动解析挂载到对应单元
- NCE1 单元映射: Lesson N → 单元 (N+1)//2；NCE2/3/4: Lesson N → 单元 N

## 重建命令

```bash
cd /data/.default/nce-site
npm run build          # 先跑 build-data.py 再 vite build
sudo rsync -a dist/index.html dist/assets/ /opt/1panel/www/sites/nce/index/
sudo rsync -a dist/data/ /opt/1panel/www/sites/nce/index/data/
sudo rsync -a data/audio/ /opt/1panel/www/sites/nce/index/audio/   # 461MB+，增量同步
```

## 构建脚本职责

`scripts/build-data.py` 读取 data/ → 输出 `public/data/index.json` + `units/{nce1,nce2,nce3,nce4}/*.json`：
- 词汇: notes 精选词优先 → 课文提取补充 → PDF 补充 → docx 补充，ECDICT 补音标
- 语法: notes 结构化优先 → PDF → NCE1 标准语法表 → NCE2 迷你笔记 → docx
- 词组/句型: notes phrases/sentencePatterns
- 训练题: gen_quiz 基于课文+词汇自动生成（8 题/课）
