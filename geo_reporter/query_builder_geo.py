"""自然语言 → gds 检索式（LLM）。"""

from __future__ import annotations

from geo_reporter.config import Settings
from geo_reporter.llm_client import chat_completion
from geo_reporter.prompts.query_translate_geo import (
    SYSTEM_GEO_QUERY,
    build_geo_query_user_prompt,
    normalize_llm_geo_query,
)


def natural_language_to_gds_query(settings: Settings, natural_language: str) -> str:
    user = build_geo_query_user_prompt(natural_language)
    raw = chat_completion(
        settings,
        SYSTEM_GEO_QUERY,
        user,
        temperature=0.15,
        flow_stage="LLM：自然语言 → gds 检索式",
    )
    q = normalize_llm_geo_query(raw)
    if not q:
        raise ValueError("模型未返回可用的 gds 检索式，请重试或改用 --raw-query 手工指定。")
    return q
