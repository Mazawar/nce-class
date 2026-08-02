# NCE 学习站（nce-class）

新概念英语（New Concept English）四册全量学习网站，纯前端单页应用。

## 在线访问

- 学习站: https://frp-shy.com:61047
- 刷题系统: https://frp-shy.com:16426/

## 功能特性

- **四册全覆盖**：NCE1 (72 单元 / 144 课)、NCE2 (48 单元 / 96 课)、NCE3 (30 单元 / 60 课)、NCE4 (24 单元 / 48 课)
- **统一课程结构**：2 课 = 1 单元，奇数课 = 课文、偶数课 = 单词语法
- **每课五板块**：课文（跟读 + 音频定位）、单词、语法、训练、资料库
- **课文横向滚动**：长句不换行，超宽横向滚动
- **按需加载**：单元数据懒加载，首次秒开
- **搜索定位**：按课号 / 标题 / 关键词搜索
- **hash 路由**：`#/nce2/5/words` 直达课 + 板块
- **移动端适配**：响应式布局 + 汉堡菜单

## 技术栈

- Vite + 原生 JS（零框架）
- 数据构建: Python（build-data.py）

## 快速开始

```bash
# 安装依赖
npm install

# 数据构建（需 data/ 目录，见 data/SOURCES.md 获取数据源）
python3 scripts/build-data.py

# 本地开发
npm run dev

# 生产构建
npm run build
```

## 目录结构

```
├── index.html          # 页面骨架
├── main.js             # 前端逻辑（路由/渲染/交互）
├── style.css           # 样式
├── vite.config.js      # Vite 配置
├── scripts/
│   ├── build-data.py   # 数据构建器（吃 data/ 生成 public/data/）
│   ├── dl_nce4.py      # NCE4 音频/LRC 下载脚本
│   ├── dl_audio.py     # 音频批量下载脚本
│   └── nce1_grammar.py # NCE1 标准语法表
└── data/
    └── SOURCES.md      # 数据来源清单（重要！大文件不在 git 里）
```

## 数据说明

数据（音频、词典、结构化笔记）体积大，**不进 git 仓库**。
所有数据源 URL 与获取方式记录在 [`data/SOURCES.md`](data/SOURCES.md)，重新部署时按文档下载即可。

主数据源：
- LiDuoMiao/new-concept-english —— 结构化笔记（词汇/词组/语法/句型）
- ECDICT —— 词典（音标/释义/柯林斯星级）
- nce.mleo.site —— 课文 LRC + 音频

## 部署

```bash
npm run build
# 部署 dist/ 到站点目录（assets/ 保持子目录层级）
sudo cp dist/index.html <站点>/index.html
sudo cp dist/assets/* <站点>/assets/
sudo rsync -a dist/data/ <站点>/data/
sudo rsync -a data/audio/ <站点>/audio/   # 音频增量同步
```
