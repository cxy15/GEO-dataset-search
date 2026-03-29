# GEO 自然语言检索与数据推荐报告

## 功能

- 自然语言（或手工）检索式 → **NCBI GEO DataSets（gds）** 检索与摘要拉取。
- 默认对标准 **HTTPS** 路径做 **HEAD** ，以自动滤过实际上未公开数据或缺失GPL文件的数据（`series_matrix`、`family.soft`），结合元数据标注 `likely_ok` / `suspect_*` / `unknown`（**不能**100% 保证矩阵非空，详见报告说明）。
- LLM 相关性分级 + **中文数据推荐报告**；**禁止**将明确 `suspect_*` 作为首选可下载分析推荐（由系统提示约束）。


## 快速开始

```bash
cd /path/to/GEO-dataset-search
python3 -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env
# 编辑 .env：ENTREZ_EMAIL、OPENAI_API_KEY、OPENAI_BASE_URL、OPENAI_MODEL 等

# 交互（推荐）
chmod +x run.sh
./run.sh
```

非交互示例：

```bash
export ENTREZ_EMAIL=you@example.com
export OPENAI_API_KEY=sk-...
export OPENAI_BASE_URL=https://api.openai.com/v1
export OPENAI_MODEL=gpt-4o-mini

.venv/bin/python -m geo_reporter "肺癌 RNA-seq 肿瘤免疫微环境" -n 15 -o report.txt
```

手工检索式（跳过「自然语言→检索式」LLM）：

```bash
.venv/bin/python -m geo_reporter -q 'lung cancer AND Homo sapiens[orgn] AND gse[entry_type]' \
  "研究意图说明（用于相关性与最终报告）" -n 20
```

仅元数据、不远程探测（更快）：

```bash
.venv/bin/python -m geo_reporter "..." --no-probe -n 30
```

## 输出

- 终端与 `logs/run_*.log`（若用 `run.sh` 的 `tee`）。
- `logs/geo_query_*.txt`、`geo_esearch_*.txt`、`geo_esummary_*.jsonl`、`retrieved_geo_*.txt`、`geo_relevance_*.json`。
- UTF-8 文本报告（`-o`）。

## 报告完成后的 GSE 交互（默认开启）

在终端交互运行时，主报告写入结束后会进入 **会话**：

- 输入 **GSE 编号**（如 `GSE12345` 或仅数字，一次只能输一个），程序拉取 NCBI **esummary** 与样本等元数据，经 **LLM** 生成：实验设计、样本概况、与检索意图的符合程度；
- 随后询问 **是否下载** 该系列的 **Series Matrix**（`GSE*_series_matrix.txt.gz`，来自 NCBI 标准 HTTPS 路径）到 `downloads/<GSE>/`；
- 输入 **q** 退出会话并结束程序。

非交互或管道场景请使用 `--no-gse-session` 跳过该步骤。

## 项目结构

```
GEO-dataset-search/
├── README.md
├── requirements.txt          # Python 依赖
├── .env.example              # 环境变量模板（复制为 .env）
├── .gitignore
├── run.sh                    # Bash 交互入口（与 PubMed 项目对齐的环境配置）
├── run.bat                   # Windows 简易入口
├── geo_reporter/             # 主包
│   ├── __main__.py           # python -m geo_reporter
│   ├── cli.py                # 命令行参数与入口
│   ├── config.py             # 自 .env 加载 ENTREZ_* / OPENAI_*
│   ├── flow_log.py             # 流程日志（stderr）
│   ├── llm_client.py           # OpenAI 兼容 Chat Completions
│   ├── text_report.py          # UTF-8 文本报告写出
│   ├── models_geo.py           # 数据结构（GSE 记录、检索结果等）
│   ├── geo_entrez_client.py    # NCBI Entrez：db=gds 检索与 esummary
│   ├── query_builder_geo.py    # 自然语言 → gds 检索式（LLM）
│   ├── availability_probe.py   # 元数据 + HTTPS HEAD 可用性标注
│   ├── series_matrix_download.py  # 下载 GSE*_series_matrix.txt.gz
│   ├── retrieval_log_geo.py    # logs/ 中间快照（query、esearch、esummary）
│   ├── relevance_scoring_geo.py
│   ├── modes_geo.py            # 主流水线：检索 → 探测 → 相关性 → 报告
│   ├── gse_interactive.py      # 报告后：按 GSE 交互解读与可选下载
│   └── prompts/                # LLM 提示模板
│       ├── query_translate_geo.py
│       ├── relevance_geo.py
│       ├── final_report_geo.py
│       └── gse_session.py
├── logs/                     # 运行生成（见 .gitignore）
└── downloads/                # GSE 交互下载的 Series Matrix（见 .gitignore）
```


## 说明

- 主检索流程**不**自动批量下载数据；仅在 **GSE 交互**中确认后，下载 **Series Matrix**（`*.txt.gz`）。「假数据 / 空矩阵」风险通过元数据 + 远程文件存在性/体积作**近似**判断。
- NCBI 要求提供 `ENTREZ_EMAIL`；可选 `NCBI_API_KEY` 提高 E-utilities 速率。

## 仓库

源码：<https://github.com/cxy15/GEO-dataset-search>
