"""元数据启发式 + NCBI GEO HTTPS 文件 HEAD 探测（不下载矩阵正文）。"""

from __future__ import annotations

import re
import urllib.error
import urllib.request

from geo_reporter.models_geo import GeoSeriesRecord

MIN_FILE_BYTES = 2048
HEAD_TIMEOUT_SEC = 10.0

_BAD_SUMMARY_KEYWORDS = (
    "private",
    "not available",
    "upon request",
    "withheld",
    "embargo",
    "to be released",
    "not yet available",
    "access restricted",
)

_GSE_ACC = re.compile(r"^(GSE\d+)$", re.IGNORECASE)
_GPL_ACC = re.compile(r"^(GPL\d+)$", re.IGNORECASE)


def _geo_parent_dir(accession: str) -> str:
    acc = accession.strip().upper()
    if acc.startswith("GSE"):
        n = int(acc[3:])
        return f"GSE{n // 1000}nnn"
    if acc.startswith("GPL"):
        n = int(acc[3:])
        return f"GPL{n // 1000}nnn"
    return ""


def _head_url(url: str) -> tuple[int | None, int | None, str | None]:
    req = urllib.request.Request(url, method="HEAD")
    try:
        with urllib.request.urlopen(req, timeout=HEAD_TIMEOUT_SEC) as resp:
            code = resp.getcode()
            cl = resp.headers.get("Content-Length")
            size: int | None
            if cl and str(cl).isdigit():
                size = int(cl)
            else:
                size = None
            return code, size, None
    except urllib.error.HTTPError as e:
        return e.code, None, None
    except Exception as e:
        return None, None, str(e)[:200]


def series_matrix_https_url(gse_accession: str) -> str:
    """NCBI GEO 标准 Series Matrix 文件 HTTPS 地址（.txt.gz）。"""
    gse = gse_accession.strip().upper()
    parent = _geo_parent_dir(gse)
    return (
        f"https://ftp.ncbi.nlm.nih.gov/geo/series/{parent}/{gse}/matrix/"
        f"{gse}_series_matrix.txt.gz"
    )


def _series_urls(gse: str) -> tuple[str, str]:
    gse_u = gse.upper()
    parent = _geo_parent_dir(gse_u)
    base = f"https://ftp.ncbi.nlm.nih.gov/geo/series/{parent}/{gse_u}"
    matrix = series_matrix_https_url(gse_u)
    soft = f"{base}/soft/{gse_u}_family.soft.gz"
    return matrix, soft


def _gpl_soft_url(gpl: str) -> str:
    parent = _geo_parent_dir(gpl)
    u = gpl.upper()
    return f"https://ftp.ncbi.nlm.nih.gov/geo/platforms/{parent}/{u}/soft/{u}_family.soft.gz"


def _metadata_suspect(rec: GeoSeriesRecord) -> tuple[bool, list[str]]:
    reasons: list[str] = []
    if rec.n_samples <= 0:
        reasons.append("n_samples 为 0 或缺失")
    if not (rec.ftp_link or "").strip():
        reasons.append("FTPLink 缺失")
    blob = f"{rec.title} {rec.summary}".lower()
    for kw in _BAD_SUMMARY_KEYWORDS:
        if kw in blob:
            reasons.append(f"摘要/标题含敏感词: {kw}")
            break
    return (len(reasons) > 0), reasons


def _file_looks_usable(code: int | None, size: int | None) -> bool:
    if code != 200:
        return False
    if size is None:
        return True
    return size >= MIN_FILE_BYTES


def annotate_record(rec: GeoSeriesRecord, *, probe_remote: bool) -> None:
    """就地写入 availability_tier、availability_notes 及探测字段。"""
    acc = (rec.accession or "").strip()

    if not probe_remote:
        m_suspect, m_reasons = _metadata_suspect(rec)
        if m_suspect:
            rec.availability_tier = "suspect_metadata"
            rec.availability_notes = "；".join(m_reasons)
        else:
            rec.availability_tier = "unknown"
            rec.availability_notes = "已跳过远程探测（--no-probe），仅元数据评估"
        return

    notes: list[str] = []
    m_suspect, m_reasons = _metadata_suspect(rec)

    if not _GSE_ACC.match(acc):
        rec.probe_gpl_status = "skipped"
        if m_suspect:
            rec.availability_tier = "suspect_metadata"
            rec.availability_notes = "；".join(m_reasons + ["非标准 GSE 编号，未做系列文件 HEAD"])
        else:
            rec.availability_tier = "unknown"
            rec.availability_notes = "非标准 GSE 编号，未做系列文件 HEAD"
        return

    matrix_u, soft_u = _series_urls(acc)
    mc, ms, me = _head_url(matrix_u)
    sc, ss, se = _head_url(soft_u)

    rec.probe_matrix_url = matrix_u
    rec.probe_matrix_status = None if mc is None else str(mc)
    rec.probe_matrix_size = ms
    rec.probe_soft_url = soft_u
    rec.probe_soft_status = None if sc is None else str(sc)
    rec.probe_soft_size = ss

    gpl = (rec.gpl or "").strip().split(",")[0].strip()
    if _GPL_ACC.match(gpl):
        gu = _gpl_soft_url(gpl)
        rec.probe_gpl_url = gu
        gc, _gs, _ = _head_url(gu)
        rec.probe_gpl_status = None if gc is None else str(gc)
        if gc == 404:
            notes.append(f"平台 {gpl} 标准路径 SOFT 为 404")
    else:
        rec.probe_gpl_status = "skipped"

    series_files_ok = _file_looks_usable(mc, ms) or _file_looks_usable(sc, ss)
    if mc == 200 and ms is not None and ms < MIN_FILE_BYTES:
        notes.append(f"series_matrix 体积过小({ms} B)")
    if sc == 200 and ss is not None and ss < MIN_FILE_BYTES:
        notes.append(f"family.soft 体积过小({ss} B)")
    if mc == 404 and sc == 404:
        notes.append("matrix 与 soft 均为 404")
    if mc is None and sc is None:
        notes.append(f"系列文件 HEAD 失败: {me or ''} {se or ''}".strip())

    if m_suspect:
        rec.availability_tier = "suspect_metadata"
        rec.availability_notes = "；".join(m_reasons + notes)
        return

    if series_files_ok:
        rec.availability_tier = "likely_ok"
        rec.availability_notes = (
            "远程探测到可访问的 series_matrix 或 family.soft；"
            "矩阵是否非空需下载后验证"
        )
        if notes:
            rec.availability_notes += "；" + "；".join(notes)
        return

    if (mc == 404 and sc == 404) or (
        mc == 200
        and ms is not None
        and ms < MIN_FILE_BYTES
        and sc == 200
        and ss is not None
        and ss < MIN_FILE_BYTES
    ):
        rec.availability_tier = "suspect_files"
        rec.availability_notes = "；".join(notes) if notes else "系列数据文件不可用或过小"
        return

    rec.availability_tier = "unknown"
    rec.availability_notes = (
        "；".join(notes) if notes else "元数据未见明显问题，但文件 HEAD 状态不明确（建议人工核对）"
    )


def annotate_all(records: list[GeoSeriesRecord], *, probe_remote: bool) -> None:
    for r in records:
        annotate_record(r, probe_remote=probe_remote)
