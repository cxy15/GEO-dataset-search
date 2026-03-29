"""从 NCBI GEO HTTPS 下载 Series Matrix File（*_series_matrix.txt.gz）。"""

from __future__ import annotations

import shutil
import urllib.error
import urllib.request
from pathlib import Path

from geo_reporter.availability_probe import series_matrix_https_url
from geo_reporter.flow_log import flow_info

DOWNLOAD_TIMEOUT_SEC = 600
CHUNK = 1024 * 1024


def download_series_matrix_txt_gz(gse_accession: str, dest_dir: Path) -> Path:
    """
    下载官方 Series Matrix（gzip 文本），保存为 ``{GSE}_series_matrix.txt.gz``。

    若系列未提供矩阵文件（常见于仅 SRA、或仅 SOFT），将抛出带 URL 的 RuntimeError。
    """
    gse = gse_accession.strip().upper()
    url = series_matrix_https_url(gse)
    dest_dir.mkdir(parents=True, exist_ok=True)
    out_path = dest_dir / f"{gse}_series_matrix.txt.gz"

    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": "geo_reporter/0.2 (NCBI GEO series matrix; bulk RNA-seq)",
        },
    )
    flow_info(f"下载 Series Matrix: {url}")
    try:
        with urllib.request.urlopen(req, timeout=DOWNLOAD_TIMEOUT_SEC) as resp:
            with out_path.open("wb") as out:
                shutil.copyfileobj(resp, out, length=CHUNK)
    except urllib.error.HTTPError as e:
        if e.code == 404:
            raise RuntimeError(
                f"未找到 Series Matrix 文件（HTTP 404）：\n  {url}\n"
                "该系列可能未提供矩阵文件，或仅提供 SOFT / 需从 SRA 下载原始测序数据。"
            ) from e
        raise RuntimeError(
            f"下载 Series Matrix 失败（HTTP {e.code}）：{url}"
        ) from e
    except OSError as e:
        raise RuntimeError(f"写入文件失败：{out_path} — {e}") from e

    flow_info(f"已保存 Series Matrix：{out_path.resolve()} ({out_path.stat().st_size} bytes)")
    return out_path
