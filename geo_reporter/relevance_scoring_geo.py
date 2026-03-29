"""对用户研究意图与 GEO 记录做相关性分级。"""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path

from geo_reporter.config import Settings
from geo_reporter.flow_log import flow_info
from geo_reporter.llm_client import chat_completion
from geo_reporter.models_geo import DatasetRelevance, GeoSeriesRecord
from geo_reporter.prompts.relevance_geo import (
    SYSTEM_RELEVANCE_GEO_ZH,
    build_relevance_geo_user_prompt,
)

_LEVEL_WEIGHT = {"高": 1.0, "中": 0.55, "低": 0.25}
RELEVANCE_BATCH_SIZE = 18


def _normalize_level(s: str | None) -> str:
    if not s:
        return "中"
    t = str(s).strip()
    if t in _LEVEL_WEIGHT:
        return t
    if t.upper() in ("HIGH", "H"):
        return "高"
    if t.upper() in ("MEDIUM", "MID", "M"):
        return "中"
    if t.upper() in ("LOW", "L"):
        return "低"
    return "中"


def _strip_markdown_fence(text: str) -> str:
    s = text.strip()
    m = re.match(r"^```(?:json|JSON)?\s*\n([\s\S]*?)\n```\s*$", s)
    if m:
        return m.group(1).strip()
    if s.startswith("```"):
        lines = s.split("\n")
        lines = lines[1:]
        if lines and lines[-1].strip().startswith("```"):
            lines = lines[:-1]
        s = "\n".join(lines).strip()
    return s


def _slice_first_json_array(s: str) -> str | None:
    start = s.find("[")
    if start < 0:
        return None
    depth = 0
    in_string = False
    escape = False
    for i in range(start, len(s)):
        c = s[i]
        if escape:
            escape = False
            continue
        if in_string:
            if c == "\\":
                escape = True
            elif c == '"':
                in_string = False
            continue
        if c == '"':
            in_string = True
            continue
        if c == "[":
            depth += 1
        elif c == "]":
            depth -= 1
            if depth == 0:
                return s[start : i + 1]
    return None


def _loads_json_array(blob: str) -> list:
    blob = blob.strip()
    dec = json.JSONDecoder()
    idx = 0
    while idx < len(blob) and blob[idx] != "[":
        idx += 1
    if idx >= len(blob):
        raise json.JSONDecodeError("未找到 JSON 数组起始 [", blob, 0)
    obj, _end = dec.raw_decode(blob, idx)
    if not isinstance(obj, list):
        raise ValueError("相关性输出应为 JSON 数组")
    return obj


def _try_repair_trailing_commas(blob: str) -> str:
    prev = None
    out = blob
    while prev != out:
        prev = out
        out = re.sub(r",(\s*[\]}])", r"\1", out)
    return out


def _parse_relevance_raw(raw: str) -> list[dict]:
    cleaned = _strip_markdown_fence(raw)
    blob = _slice_first_json_array(cleaned)
    if blob is None:
        blob = cleaned.strip()
    errors: list[str] = []
    for attempt in (
        lambda b: _loads_json_array(b),
        lambda b: _loads_json_array(_try_repair_trailing_commas(b)),
    ):
        try:
            data = attempt(blob)
            break
        except (json.JSONDecodeError, ValueError) as e:
            errors.append(str(e))
            data = None
    else:
        raise ValueError(
            "相关性 JSON 无法解析: " + ("; ".join(errors) if errors else "unknown")
        ) from None
    return [x for x in data if isinstance(x, dict)]


def align_relevances(
    records: list[GeoSeriesRecord],
    parsed: list[dict],
) -> list[DatasetRelevance]:
    by_acc: dict[str, dict] = {}
    for row in parsed:
        a = str(row.get("accession", "")).strip().upper()
        if a:
            by_acc[a] = row

    out: list[DatasetRelevance] = []
    for r in records:
        acc = (r.accession or "").strip() or "未知"
        key = acc.upper()
        row = by_acc.get(key)
        level = _normalize_level(row.get("level") if row else None)
        rationale = ""
        if row and row.get("rationale"):
            rationale = str(row["rationale"]).strip()
        if not rationale:
            rationale = "（模型未给出理由）" if not row else "（无）"
        w = _LEVEL_WEIGHT.get(level, 0.55)
        out.append(
            DatasetRelevance(
                accession=acc,
                level=level,
                weight=w,
                rationale=rationale,
            )
        )
    return out


def _default_chunk(chunk: list[GeoSeriesRecord]) -> list[dict]:
    return [
        {
            "accession": (r.accession or "").strip() or "未知",
            "level": "中",
            "rationale": "（本批分级 JSON 解析失败，默认中等相关）",
        }
        for r in chunk
    ]


def score_geo_relevance(
    settings: Settings,
    user_intent: str,
    term: str,
    records: list[GeoSeriesRecord],
) -> list[DatasetRelevance]:
    if not records:
        return []
    n = len(records)
    merged: list[dict] = []
    n_batches = (n + RELEVANCE_BATCH_SIZE - 1) // RELEVANCE_BATCH_SIZE
    if n_batches > 1:
        flow_info(
            f"相关性分级：共 {n} 条，分 {n_batches} 批（每批最多 {RELEVANCE_BATCH_SIZE} 条）"
        )

    for start in range(0, n, RELEVANCE_BATCH_SIZE):
        chunk = records[start : start + RELEVANCE_BATCH_SIZE]
        batch_idx = start // RELEVANCE_BATCH_SIZE + 1
        user = build_relevance_geo_user_prompt(user_intent, term, chunk)
        raw = chat_completion(
            settings,
            SYSTEM_RELEVANCE_GEO_ZH,
            user,
            temperature=0.2,
            flow_stage=f"LLM：数据集相关性分级（第 {batch_idx}/{n_batches} 批）",
        )
        try:
            parsed = _parse_relevance_raw(raw)
            merged.extend(parsed)
        except (json.JSONDecodeError, ValueError) as e:
            flow_info(f"相关性 JSON 解析失败（第 {batch_idx}/{n_batches} 批），本批按「中」处理：{e}")
            merged.extend(_default_chunk(chunk))

    return align_relevances(records, merged)


def save_relevance_geo_to_logs(
    term: str,
    *,
    user_intent: str,
    records: list[GeoSeriesRecord],
    relevances: list[DatasetRelevance],
) -> Path:
    log_dir = Path.cwd() / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    path = log_dir / f"geo_relevance_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    iso_now = datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")
    payload = {
        "generated_at_local": iso_now,
        "user_intent": user_intent,
        "gds_term": term,
        "items": [],
    }
    for r, rel in zip(records, relevances):
        payload["items"].append(
            {
                "accession": r.accession,
                "availability_tier": r.availability_tier,
                "level": rel.level,
                "weight": rel.weight,
                "rationale": rel.rationale,
            }
        )
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8", newline="\n")
    return path
