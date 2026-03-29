"""GEO 检索 + 推荐报告流水线。"""

from __future__ import annotations

from pathlib import Path

from geo_reporter import geo_entrez_client
from geo_reporter.availability_probe import annotate_all
from geo_reporter.config import Settings
from geo_reporter.flow_log import flow_info
from geo_reporter.llm_client import chat_completion
from geo_reporter.prompts.final_report_geo import (
    SYSTEM_FINAL_REPORT_ZH,
    build_final_report_user_prompt,
)
from geo_reporter.query_builder_geo import natural_language_to_gds_query
from geo_reporter.relevance_scoring_geo import (
    save_relevance_geo_to_logs,
    score_geo_relevance,
)
from geo_reporter.retrieval_log_geo import (
    save_geo_esearch_log,
    save_geo_esummary_jsonl,
    save_geo_query_log,
    save_retrieved_geo_snapshot,
)
from geo_reporter.models_geo import GeoSearchRunOutcome
from geo_reporter.text_report import write_report_txt


def _emit_final_search_term(term: str) -> None:
    flow_info("实际用于检索的 gds 表达式（完整）：\n" + term.strip())


def run_search(
    settings: Settings,
    user_intent: str,
    *,
    raw_query: str | None,
    retmax: int,
    output_path: Path,
    probe_remote: bool,
) -> GeoSearchRunOutcome:
    if raw_query:
        term = raw_query.strip()
        flow_info("已使用手工检索式（--raw-query），跳过「自然语言 → gds 检索式」的 LLM。")
        used_raw = True
    else:
        term = natural_language_to_gds_query(settings, user_intent)
        used_raw = False

    qpath = save_geo_query_log(
        user_intent=user_intent,
        final_term=term,
        used_raw_query=used_raw,
    )
    flow_info(f"已保存检索式快照：{qpath.resolve()}")

    _emit_final_search_term(term)

    geo_entrez_client.configure_entrez(settings.entrez_email, settings.ncbi_api_key)
    result = geo_entrez_client.search_gds(term, retmax=retmax)

    es = save_geo_esearch_log(
        term=term,
        total_count=result.total_count,
        id_list=result.retrieved_ids,
    )
    flow_info(f"已保存 esearch 快照：{es.resolve()}")

    annotate_all(result.records, probe_remote=probe_remote)

    ej = save_geo_esummary_jsonl(result.records)
    flow_info(f"已保存 esummary（jsonl）：{ej.resolve()}")

    snap = save_retrieved_geo_snapshot(
        result,
        extra_meta={"user_intent": user_intent, "probe_remote": str(probe_remote)},
    )
    flow_info(f"已保存检索快照（相关性分析前）：{snap.resolve()}")

    relevances = score_geo_relevance(settings, user_intent, term, result.records)
    rlog = save_relevance_geo_to_logs(
        term,
        user_intent=user_intent,
        records=result.records,
        relevances=relevances,
    )
    flow_info(f"已保存相关性 JSON：{rlog.resolve()}")

    user_prompt = build_final_report_user_prompt(
        user_intent,
        term,
        result.total_count,
        result.records,
        relevances,
    )
    report = chat_completion(
        settings,
        SYSTEM_FINAL_REPORT_ZH,
        user_prompt,
        temperature=0.35,
        flow_stage="LLM：生成中文数据推荐报告",
    )
    safe_title = f"「GEO 数据推荐报告」{user_intent.strip()[:100]}"
    flow_info("开始 | 写入报告文本文件")
    path = write_report_txt(safe_title, report, output_path)
    flow_info(f"完成 | 写入报告文本文件：{path.resolve()}")
    return GeoSearchRunOutcome(report_path=path, gds_term=term, user_intent=user_intent)
