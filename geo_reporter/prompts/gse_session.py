"""GSE 单条详情：实验设计、样本与意图匹配。"""

from __future__ import annotations

import json

from geo_reporter.models_geo import GeoSeriesRecord

SYSTEM_GSE_DETAIL_ZH = (
    "你是高通量组学数据策展助手。根据用户提供的 NCBI GEO Series 元数据（标题、摘要、样本列表等），"
    "用简体中文结构化输出以下内容（使用清晰的小标题与条目）："
    "1）实验设计：研究目的、实验因素、对照与处理、平台与技术类型；"
    "2）样本情况：样本量、分组线索（若元数据中可识别）、物种与数据类型；"
    "3）与用户检索意图的符合程度：给出「高/中/低」之一，并简述理由；"
    "4）数据可用性提示：若摘要或元数据暗示未公开、私有、需联系作者等，须明确提醒。"
    "不要编造元数据中不存在的事实；信息不足时写明「未在摘要中体现」。"
)


def build_gse_detail_user_prompt(
    user_intent: str,
    gds_term_from_search: str,
    record: GeoSeriesRecord,
    raw_summary_plain: dict,
) -> str:
    """将 esummary 原始字段（可含 Samples 列表）一并交给模型。"""
    extra = json.dumps(raw_summary_plain, ensure_ascii=False, indent=2)
    if len(extra) > 12000:
        extra = extra[:12000] + "\n…（raw_summary 已截断）"
    base = record.to_llm_text()
    return f"""用户当前的研究意图（来自本次 GEO 检索会话）：
{user_intent.strip()}

本次会话使用的 Entrez gds 检索式（供对照，非本 GSE 唯一描述）：
{gds_term_from_search.strip()}

--- 本条 GSE 的结构化摘要（geo_reporter 解析） ---
{base}

--- NCBI esummary 原始字段（JSON，含样本列表等） ---
{extra}
"""
