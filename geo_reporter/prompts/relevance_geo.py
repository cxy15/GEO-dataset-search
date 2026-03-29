"""数据集与用户研究意图的相关性分级。"""

from __future__ import annotations

from geo_reporter.models_geo import GeoSeriesRecord

SYSTEM_RELEVANCE_GEO_ZH = (
    "你是生物医学高通量数据检索评估助手。用户会给出研究意图，以及若干条来自 NCBI GEO（gds）的数据集摘要。"
    "每条记录带有「可用性分级」availability_tier：likely_ok 表示更可能具备可下载的分析文件；"
    "suspect_metadata 表示元数据层面可疑（如样本数为 0、未公开等）；suspect_files 表示远程文件探测不佳；"
    "unknown 表示不确定。"
    "请逐条判断该数据集与用户研究意图的贴合程度（高/中/低），并给一句中文理由。"
    "不要编造摘要中不存在的内容。"
    "输出要求：仅输出一个 JSON 数组，不要使用 Markdown 代码围栏，不要在 JSON 前后添加任何说明文字。"
    "JSON 中键名与字符串值用英文双引号；rationale 不超过 40 个汉字，勿含英文双引号。"
)


def _compact_block(r: GeoSeriesRecord, index: int, total: int) -> str:
    summ = (r.summary or "").strip()
    if len(summ) > 1500:
        summ = summ[:1500] + "…（摘要截断）"
    acc = (r.accession or "").strip() or "未知"
    return (
        f"[{index}/{total}] Accession={acc}\n"
        f"标题: {r.title}\n"
        f"物种: {r.taxon}  样本数: {r.n_samples}  GPL: {r.gpl}\n"
        f"可用性分级: {r.availability_tier}\n"
        f"可用性说明: {r.availability_notes or '（无）'}\n"
        f"摘要:\n{summ if summ else '（无摘要）'}\n"
    )


def build_relevance_geo_user_prompt(user_intent: str, term: str, records: list[GeoSeriesRecord]) -> str:
    n = len(records)
    blocks = [_compact_block(r, i, n) for i, r in enumerate(records, start=1)]
    return f"""用户研究意图（相关性判据）：
{user_intent.strip()}

本次使用的 Entrez gds 检索式：
{term.strip()}

本批共 {n} 条数据集，请为每一条输出一个 JSON 对象，字段如下：
- "accession": 字符串，与下方记录中的 Accession 完全一致（如 GSE123456）
- "level": 必须是 "高"、"中"、"低" 之一
- "rationale": 一句极短理由（中文，不超过 40 字）

将所有对象放入一个 JSON 数组，顺序与本批列表顺序一致，且必须覆盖本批全部 {n} 条。

数据集列表：
{"".join(blocks)}
"""
