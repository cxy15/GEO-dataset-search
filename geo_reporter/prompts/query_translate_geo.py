"""自然语言 → Entrez gds 检索式。"""

from __future__ import annotations

import re

SYSTEM_GEO_QUERY = (
    "你是 NCBI GEO DataSets（Entrez db=gds）检索助手。你的唯一任务是：根据用户的自然语言研究意图，"
    "写出合法、可执行的 Entrez 检索表达式（单行）。"
    "应优先使用 GEO 常用字段：如 gse[entry_type] 或 gds[entry_type]、Homo sapiens[orgn]、"
    "[title]、[description]、[gdstype]（如 expression profiling by high throughput sequencing[gdstype]）。"
    "不要输出解释、寒暄或 Markdown；不要编造不存在的字段名。"
)


def build_geo_query_user_prompt(natural_language: str) -> str:
    text = natural_language.strip()
    return f"""用户的研究意图与数据需求（可为中文或英文自然语言）：
{text}

请转换为一条可在 NCBI Entrez 的 gds 数据库中使用的检索表达式（单行字符串）。
要求：
- 仅输出检索式本身，不要序号、不要前后缀说明。
- 若目标是找系列（GSE），建议包含 gse[entry_type] 与物种、技术类型等条件的 AND 组合。
- 避免单条过宽导致大量无关记录。"""


def normalize_llm_geo_query(raw: str) -> str:
    s = raw.strip()
    if not s:
        return ""
    m = re.match(r"^```(?:\w*)?\s*\n([\s\S]*?)\n```\s*$", s)
    if m:
        s = m.group(1).strip()
    line = s.split("\n", 1)[0].strip()
    for prefix in ("Query:", "检索式:", "Answer:", "表达式:", "Entrez:"):
        if line.lower().startswith(prefix.lower()):
            line = line[len(prefix) :].strip()
    if (line.startswith('"') and line.endswith('"')) or (line.startswith("'") and line.endswith("'")):
        inner = line[1:-1].strip()
        if inner and "\n" not in inner:
            line = inner
    return line.strip()
