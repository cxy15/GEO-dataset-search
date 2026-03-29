"""NCBI E-utilities：GEO DataSets（db=gds）检索与 esummary。"""

from __future__ import annotations

import re
from typing import Any

from Bio import Entrez

from geo_reporter.flow_log import flow_info
from geo_reporter.models_geo import GseFetchResult, GeoSearchResult, GeoSeriesRecord

ESUMMARY_BATCH = 200


def configure_entrez(email: str, ncbi_api_key: str | None = None) -> None:
    Entrez.email = email
    Entrez.tool = "geo_reporter"
    Entrez.api_key = ncbi_api_key.strip() if ncbi_api_key else None


def _first(rec: dict[str, Any], *keys: str) -> str:
    for k in keys:
        if k not in rec or rec[k] is None:
            continue
        v = rec[k]
        if isinstance(v, list):
            if not v:
                continue
            if k == "PubMedIds" and all(
                isinstance(x, (int, str)) for x in v
            ):
                return ",".join(str(x) for x in v)
            v = v[0]
        s = str(v).strip()
        if s:
            return s
    return ""


def _int_samples(rec: dict[str, Any]) -> int:
    if "n_samples" in rec and rec["n_samples"] is not None:
        try:
            return int(rec["n_samples"])
        except (TypeError, ValueError):
            pass
    raw = _first(rec, "N_samples", "samples")
    if raw:
        try:
            return int(float(raw))
        except ValueError:
            pass
    samp = rec.get("Samples")
    if isinstance(samp, list) and samp:
        return len(samp)
    return 0


def _normalize_gpl(raw: str) -> str:
    s = (raw or "").strip()
    if not s:
        return ""
    if s.upper().startswith("GPL"):
        return s.upper()
    if s.isdigit():
        return f"GPL{s}"
    return s


def normalize_gse_accession(user_input: str) -> str | None:
    """将用户输入规范为 GSE 编号，如 12345、GSE12345。"""
    s = (user_input or "").strip().upper()
    if not s:
        return None
    m = re.match(r"^(?:GSE)?(\d+)$", s)
    if not m:
        return None
    return f"GSE{m.group(1)}"


def _items_from_esummary(summaries: Any) -> list[Any]:
    if isinstance(summaries, list):
        return summaries
    if isinstance(summaries, dict):
        if "DocumentSummarySet" in summaries:
            dss = summaries["DocumentSummarySet"]
            if isinstance(dss, dict) and "DocumentSummary" in dss:
                ds = dss["DocumentSummary"]
                return ds if isinstance(ds, list) else [ds]
            return []
        return [summaries]
    return []


def _to_plain_dict(obj: Any) -> Any:
    """将 Entrez 解析对象转为可 JSON/文本序列化的结构。"""
    if obj is None:
        return None
    if isinstance(obj, (str, int, float, bool)):
        return obj
    if isinstance(obj, dict):
        return {str(k): _to_plain_dict(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_to_plain_dict(x) for x in obj]
    try:
        return dict(obj)
    except (TypeError, ValueError):
        return str(obj)


def _summary_dict_to_record(gds_id: str, rec: dict[str, Any]) -> GeoSeriesRecord:
    gpl_raw = _first(rec, "GPL", "gpl", "Gpl")
    return GeoSeriesRecord(
        gds_id=gds_id,
        accession=_first(rec, "Accession", "accession"),
        title=_first(rec, "title", "Title"),
        summary=_first(rec, "summary", "Summary"),
        taxon=_first(rec, "taxon", "Taxon", "organism"),
        gpl=_normalize_gpl(gpl_raw),
        n_samples=_int_samples(rec),
        gds_type=_first(rec, "gdsType", "GDS_type"),
        ptech_type=_first(rec, "ptechType", "PtechType"),
        pubmed_ids=_first(rec, "PubMedIds", "pubmedids"),
        ftp_link=_first(rec, "FTPLink", "FtpLink", "ftp"),
    )


def fetch_gse_by_accession(accession: str) -> GseFetchResult | None:
    """
    按 GSE 编号从 gds 检索并取 esummary（单条）。
    若未找到记录则返回 None。
    """
    acc = normalize_gse_accession(accession)
    if not acc:
        return None
    handle = Entrez.esearch(db="gds", term=f"{acc}[accn]", retmax=10)
    search = Entrez.read(handle)
    handle.close()
    ids = search.get("IdList", [])
    if not ids:
        return None
    h2 = Entrez.esummary(db="gds", id=ids[0])
    summaries = Entrez.read(h2)
    h2.close()
    items = _items_from_esummary(summaries)
    if not items:
        return None
    item = items[0]
    if not isinstance(item, dict):
        return None
    gid = str(item.get("uid", "") or item.get("Id", "") or ids[0]).strip()
    rec = _summary_dict_to_record(gid, item)
    if rec.accession.strip().upper() != acc:
        for it in items[1:]:
            if not isinstance(it, dict):
                continue
            tacc = _first(it, "Accession", "accession").strip().upper()
            if tacc == acc:
                item = it
                gid = str(item.get("uid", "") or item.get("Id", "") or "").strip() or gid
                rec = _summary_dict_to_record(gid, item)
                break
    if rec.accession.strip().upper() != acc:
        return None
    plain = _to_plain_dict(item)
    if not isinstance(plain, dict):
        plain = {"raw": plain}
    return GseFetchResult(record=rec, raw_summary=plain)


def search_gds(term: str, *, retmax: int) -> GeoSearchResult:
    flow_info(f"NCBI esearch(db=gds) retmax={retmax}")
    handle = Entrez.esearch(db="gds", term=term, retmax=retmax, sort="relevance")
    search = Entrez.read(handle)
    handle.close()

    id_list = [str(x).strip() for x in search.get("IdList", []) if str(x).strip()]
    count_raw = search.get("Count", "0")
    try:
        total_count = int(str(count_raw))
    except ValueError:
        total_count = len(id_list)

    if not id_list:
        return GeoSearchResult(query=term, total_count=total_count, retrieved_ids=[], records=[])

    records: list[GeoSeriesRecord] = []
    for start in range(0, len(id_list), ESUMMARY_BATCH):
        batch = id_list[start : start + ESUMMARY_BATCH]
        ids = ",".join(batch)
        flow_info(
            f"NCBI esummary(db=gds) 批次 {start // ESUMMARY_BATCH + 1}，"
            f"条数 {len(batch)}"
        )
        h2 = Entrez.esummary(db="gds", id=ids)
        summaries = Entrez.read(h2)
        h2.close()

        items = _items_from_esummary(summaries)

        for i, item in enumerate(items):
            if not isinstance(item, dict):
                continue
            gid = (
                str(item.get("uid", "") or item.get("Id", "") or "").strip()
                or (batch[i] if i < len(batch) else "")
            )
            if not gid and i < len(batch):
                gid = batch[i]
            records.append(_summary_dict_to_record(gid, item))

    return GeoSearchResult(
        query=term,
        total_count=total_count,
        retrieved_ids=id_list,
        records=records,
    )
