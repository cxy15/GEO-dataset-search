"""GEO 检索中间变量落盘（logs/）。"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from geo_reporter.models_geo import GeoSearchResult, GeoSeriesRecord


def _stamp() -> str:
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def save_geo_query_log(
    *,
    user_intent: str,
    final_term: str,
    used_raw_query: bool,
) -> Path:
    log_dir = Path.cwd() / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    path = log_dir / f"geo_query_{_stamp()}.txt"
    iso_now = datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")
    lines = [
        "# GEO 检索式快照",
        f"# generated_at_local: {iso_now}",
        f"used_raw_query: {used_raw_query}",
        f"user_intent: {user_intent.replace(chr(10), ' ').strip()}",
        f"gds_term: {final_term.replace(chr(10), ' ').strip()}",
        "",
    ]
    path.write_text("\n".join(lines), encoding="utf-8", newline="\n")
    return path


def save_geo_esearch_log(
    *,
    term: str,
    total_count: int,
    id_list: list[str],
) -> Path:
    log_dir = Path.cwd() / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    path = log_dir / f"geo_esearch_{_stamp()}.txt"
    iso_now = datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")
    preview = ", ".join(id_list[:80])
    if len(id_list) > 80:
        preview += f", ...（共 {len(id_list)} 个）"
    lines = [
        "# GEO esearch(db=gds) 快照",
        f"# generated_at_local: {iso_now}",
        f"Count: {total_count}",
        f"term: {term}",
        f"IdList: {preview}",
        "",
    ]
    path.write_text("\n".join(lines), encoding="utf-8", newline="\n")
    return path


def save_geo_esummary_jsonl(records: list[GeoSeriesRecord]) -> Path:
    log_dir = Path.cwd() / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    path = log_dir / f"geo_esummary_{_stamp()}.jsonl"
    iso_now = datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")

    def row(r: GeoSeriesRecord) -> dict:
        return {
            "generated_at_local": iso_now,
            "gds_id": r.gds_id,
            "accession": r.accession,
            "title": r.title,
            "summary": r.summary[:2000] if r.summary else "",
            "taxon": r.taxon,
            "gpl": r.gpl,
            "n_samples": r.n_samples,
            "gds_type": r.gds_type,
            "ptech_type": r.ptech_type,
            "pubmed_ids": r.pubmed_ids,
            "ftp_link": r.ftp_link,
            "availability_tier": r.availability_tier,
            "availability_notes": r.availability_notes,
            "probe_matrix_url": r.probe_matrix_url,
            "probe_matrix_status": r.probe_matrix_status,
            "probe_matrix_size": r.probe_matrix_size,
            "probe_soft_url": r.probe_soft_url,
            "probe_soft_status": r.probe_soft_status,
            "probe_soft_size": r.probe_soft_size,
            "probe_gpl_url": r.probe_gpl_url,
            "probe_gpl_status": r.probe_gpl_status,
        }

    with path.open("w", encoding="utf-8", newline="\n") as f:
        for r in records:
            f.write(json.dumps(row(r), ensure_ascii=False) + "\n")
    return path


def save_retrieved_geo_snapshot(
    result: GeoSearchResult,
    *,
    extra_meta: dict[str, str] | None = None,
) -> Path:
    """人类可读快照，顺序与送入 LLM 一致。"""
    log_dir = Path.cwd() / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    path = log_dir / f"retrieved_geo_{_stamp()}.txt"
    iso_now = datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")
    recs = result.records
    total = len(recs)

    header = [
        "# GEO 检索快照（送入相关性 LLM 前）",
        f"# generated_at_local: {iso_now}",
        f"gds_query: {result.query.replace(chr(10), ' ').strip()}",
        f"database_count_total: {result.total_count}",
        f"esearch_returned_ids: {len(result.retrieved_ids)}",
        f"esummary_records: {total}",
    ]
    if extra_meta:
        for k, v in extra_meta.items():
            header.append(f"{k}: {v}")

    blocks: list[str] = ["\n".join(header) + "\n\n"]
    blocks.append("----- 数据集列表（序号与 LLM 输入一致） -----\n\n")

    for i, r in enumerate(recs, start=1):
        blocks.append("=" * 78 + "\n")
        blocks.append(f"序号: {i} / {total}\n")
        blocks.append(f"gds_id: {r.gds_id}\n")
        blocks.append(f"Accession: {r.accession}\n")
        blocks.append(f"标题: {r.title}\n")
        blocks.append(f"物种: {r.taxon}\n")
        blocks.append(f"GPL: {r.gpl}\n")
        blocks.append(f"样本数: {r.n_samples}\n")
        blocks.append(f"gdsType: {r.gds_type}\n")
        blocks.append(f"可用性: {r.availability_tier}\n")
        blocks.append(f"可用性说明: {r.availability_notes}\n")
        blocks.append(f"FTPLink: {r.ftp_link or '（无）'}\n")
        blocks.append("摘要:\n")
        blocks.append((r.summary or "（无）") + "\n\n")

    path.write_text("".join(blocks), encoding="utf-8", newline="\n")
    return path
