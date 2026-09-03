<div align="center">

# 🥗 NutriMentor

**AI 营养教学导师平台 —— 同一份知识库，三种教学人格**

*One knowledge base. Three ways of teaching.*

[![CI](https://img.shields.io/badge/CI-passing-brightgreen)](.github/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Python 3.10+](https://img.shields.io/badge/Python-3.10%2B-3776AB)](pyproject.toml)
[![PRs Welcome](https://img.shields.io/badge/PRs-welcome-ff69b4)](CONTRIBUTING.md)
[![Code style: ruff](https://img.shields.io/badge/Code%20style-ruff-261230)](ruff.toml)
[![Tests](https://img.shields.io/badge/Tests-22%20passing-success)](tests/)

*Hybrid RAG · Persona Tutoring · Streaming · Citation-grounded · Anti-hallucination gate*

[快速开始](#-快速开始) · [架构](docs/ARCHITECTURE.md) · [贡献指南](CONTRIBUTING.md) · [报告问题](../../issues)

</div>

---

## 为什么是 NutriMentor？

通用 LLM 回答营养问题时的两大痛点：**编造文献**和**不区分受众**。
NutriMentor 用一套工程化的 RAG 管线解决：

| 痛点 | NutriMentor 方案 |
|------|-----------------|
| LLM 幻觉引用不存在的文献 | 检索限定语料 + 引用必须来自索引文档 + **相关性阈值拒答** |
| 同一个答案讲给儿童和研究生听 | **三人格引擎**：学生版 🧒 / 教师版 🎓 / 科研版 🔬 |
| 专业术语检索不到（"维D"≠"维生素D3"） | **混合检索**：BGE 稠密 + BM25 词法 + RRF 融合 + 领域同义词扩展 |
| 只给一段话看不到依据 | **来源卡片**随答附上，相关度百分比，PMID 直达 PubMed |
| 长回答等待焦虑 | **SSE 流式输出**，逐字呈现 |
| 重复提问要重述背景 | **SQLite 会话持久化**，重启不丢，多轮追问 |

## ✨ 核心特性

- 🔀 **混合检索** — FAISS/BGE 稠密 + BM25/jieba 稀疏 + Reciprocal Rank Fusion，可选 bge-reranker 精排
- 👥 **三人格教学** — 一套内核，三种话术；前端一键切换，配色随人格变化
- 🌊 **流式输出** — SSE 逐 token 推送，来源先行
- 💬 **会话记忆** — SQLite 持久化（WAL），重启不丢、线程安全、自动过期清理
- 🛡️ **反幻觉闸门** — 语料未覆盖即明确拒答，教育产品不赌运气
- 📊 **离线评估** — `nutrimentor evaluate` 输出 Recall@K / MRR，改检索有据可依
- 🩺 **环境诊断** — `nutrimentor doctor` 一键体检，issue 排障神器
- 🔑 **零密钥仓库** — 凭据全走 `.env`，pre-commit + CI 双重密钥扫描
- 🐳 **一键部署** — Dockerfile（非 root + healthcheck）+ compose + PyPI 发布流水线

## 🚀 快速开始

### pip 安装（推荐）

```bash
git clone https://github.com/GOOD-123-CPU/nutrimentor.git
cd nutrimentor
pip install -e .

cp .env.example .env          # 填入你的 LLM_API_KEY（任何 OpenAI 兼容接口）
nutrimentor download-model    # BGE 嵌入模型，约 1.3GB，国内自动加速
nutrimentor ingest            # 构建索引（首次自动放入示例数据）
nutrimentor serve             # → http://127.0.0.1:8080
```

### Docker

```bash
cp .env.example .env && docker compose up --build
```

### 终端聊天

```bash
nutrimentor chat --persona teacher
```

<!-- TODO: replace with real screenshots after first run
## 📸 界面一览

| 学生版 | 教师版 | 科研版 |
|--------|--------|--------|
| ![student](assets/screenshot_student.png) | ![teacher](assets/screenshot_teacher.png) | ![researcher](assets/screenshot_researcher.png) |
-->

## 🏗️ 架构一览

```
data/raw (xlsx/csv/docx/md/pdf)
    │  nutrimentor ingest
    ▼
FAISS 稠密索引 ─┐
BM25 词法索引 ─┤→ RRF 融合 → 教学文档加权 → [可选重排] → 阈值闸门
                │
                ▼
MentorEngine（人格提示词 + SQLite 会话历史）→ LLM
                │
        ┌───────┴────────┐
        ▼                ▼
  REST /api/ask    SSE /api/ask/stream
  /student /teacher /researcher
```

深入阅读：[docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)（设计决策与模块职责）。

## 📥 导入你自己的知识库

```bash
# 从 PubMed 拉取公开元数据（不抓全文，合规）
python scripts/fetch_pubmed.py "child nutrition gut microbiota" --max 100 \
    --out data/raw/pubmed_child_nutrition.csv

nutrimentor ingest    # 重建索引
```

或自行准备 CSV/XLSX（列名大小写不敏感）：
`PMID | Title | Authors | Journal | Year | Abstract | Impact Factor`
教学文档直接放 `.docx` / `.md`（PDF 需 `pip install PyPDF2`）。

## 🧪 开发与质量

```bash
pip install -e ".[dev]"
make test        # 22 个离线单元测试（无网络/无模型依赖）
make lint        # ruff（E/W/F/I/B/UP/SIM/C4 规则集）
nutrimentor doctor      # 环境体检
nutrimentor evaluate    # 检索质量评估（Recall@K / MRR）
```

CI 在 Python 3.10 / 3.11 / 3.12 上运行 lint + tests + Docker build。

## ⚙️ 关键配置

| 变量 | 说明 | 默认 |
|------|------|------|
| `LLM_API_KEY` | LLM 密钥（**必填**） | — |
| `LLM_BASE_URL` | OpenAI 兼容接口 | `https://api.deepseek.com` |
| `NM_HYBRID_K` | 融合前候选池 | `20` |
| `NM_TOP_K` | 进入提示词文档数 | `5` |
| `NM_RELEVANCE_THRESHOLD` | 拒答阈值 | `0.25` |
| `NM_RERANKER` | 启用精排 | `0` |
| `NM_MEMORY_TURNS` | 会话记忆轮数 | `6` |

完整列表见 [.env.example](.env.example)。

## 🗺️ Roadmap

- [x] 三人格引擎 / 混合检索 / 流式 / 会话持久化
- [x] 离线评估框架 / doctor 诊断
- [ ] Web 管理后台（语料上传、用户管理、审计日志）
- [ ] 多语言语料与英文界面
- [ ] 引用自动校验（LLM 输出与检索来源一致性检查）

## 🤝 参与贡献

好点子从 [Discussion](../../discussions) 开始，代码从 [good first issue](../../issues?q=is%3Aissue+is%3Aopen+label%3A%22good+first+issue%22) 开始。
请阅读 [CONTRIBUTING.md](CONTRIBUTING.md) 与 [行为准则](CODE_OF_CONDUCT.md)。
安全问题请走 [SECURITY.md](SECURITY.md) 渠道私下报告。

## ⚖️ 版权与数据合规

- 仓库**不含**任何爬取文章、论文全文或第三方版权内容
- 内置示例数据均为本项目**原创**，可自由使用
- PubMed 元数据经官方 [E-utilities](https://www.ncbi.nlm.nih.gov/books/NBK25499/) 获取
- AI 生成内容仅供教学参考，**不构成医疗建议**

## ⭐ Star History

[![Star History Chart](https://api.star-history.com/svg?repos=GOOD-123-CPU/nutrimentor&type=Date)](https://star-history.com/#GOOD-123-CPU/nutrimentor&Date)

## 📄 License

[MIT](LICENSE) © 2026 NutriMentor Contributors

<div align="center">

**如果 NutriMentor 对你的教学或科研有帮助，请点一个 ⭐ —— 这是开源作者最大的动力**

</div>
