"""最终中文数据推荐报告。"""

from __future__ import annotations

from geo_reporter.models_geo import DatasetRelevance, GeoSeriesRecord

SYSTEM_FINAL_REPORT_ZH = (
    "你是生物医学数据分析顾问，协助用户从 NCBI GEO 公共数据中筛选可用于下游分析的数据集。"
    "你必须遵守："
    "1) 「首选推荐」仅限 availability_tier 为 likely_ok 的数据集；"
    "若为 unknown，仅可在说明中作为备选并提示需人工核对下载；"
    "2) 严禁将 suspect_metadata 或 suspect_files 列为「首选可下载、可直接用于矩阵分析」的推荐；"
    "这些条目只能出现在「不建议 / 需警惕」章节并写明原因；"
    "3) 说明本报告基于元数据与远程文件体积/存在性探测，无法 100% 保证矩阵非空；"
    "4) 使用简体中文，结构清晰，使用小标题与条目列表。"
)


def build_final_report_user_prompt(
    user_intent: str,
    gds_term: str,
    total_count: int,
    records: list[GeoSeriesRecord],
    relevances: list[DatasetRelevance],
) -> str:
    lines: list[str] = [
        f"用户研究意图：\n{user_intent.strip()}",
        "",
        f"检索式（Entrez gds）：\n{gds_term.strip()}",
        f"数据库报告总命中数（estimate）：{total_count}",
        f"本次拉取并分析条数：{len(records)}",
        "",
        "请基于下列每条数据的摘要、可用性分级与相关性等级，撰写「数据推荐报告」。",
        "",
        "----- 数据集与相关性 -----",
        "",
    ]
    rel_by = {x.accession.strip().upper(): x for x in relevances}

    for i, rec in enumerate(records, start=1):
        acc = rec.accession.strip()
        rel = rel_by.get(acc.upper())
        lvl = rel.level if rel else "中"
        why = rel.rationale if rel else ""
        lines.append(f"{i}. {acc} | 相关性:{lvl} | 可用性:{rec.availability_tier}")
        lines.append(f"   标题: {rec.title}")
        lines.append(f"   相关性理由: {why}")
        lines.append(f"   可用性说明: {rec.availability_notes}")
        lines.append("")

    return "\n".join(lines)
