"""报告生成后的交互：按 GSE 查看详情、LLM 解读、可选下载。"""

from __future__ import annotations

import sys
from pathlib import Path

from geo_reporter import geo_entrez_client
from geo_reporter.availability_probe import annotate_record
from geo_reporter.config import Settings
from geo_reporter.flow_log import flow_info
from geo_reporter.llm_client import chat_completion
from geo_reporter.prompts.gse_session import (
    SYSTEM_GSE_DETAIL_ZH,
    build_gse_detail_user_prompt,
)
from geo_reporter.series_matrix_download import download_series_matrix_txt_gz


def _download_series_matrix(accession: str, destdir: Path) -> Path:
    """下载 NCBI 标准路径下的 ``GSE*_series_matrix.txt.gz``。"""
    acc = accession.strip().upper()
    target = destdir / acc
    return download_series_matrix_txt_gz(acc, target)


def _fetch_and_probe(accession: str) -> GseFetchResult | None:
    fr = geo_entrez_client.fetch_gse_by_accession(accession)
    if fr is None:
        return None
    annotate_record(fr.record, probe_remote=True)
    return fr


def run_session(
    settings: Settings,
    user_intent: str,
    gds_term_from_search: str,
    *,
    download_root: Path | None = None,
) -> None:
    """
    从 stdin 循环读取 GSE；q 退出。
    download_root 默认当前工作目录下的 downloads。
    """
    root = download_root or (Path.cwd() / "downloads")
    print(
        "\n========== GSE 详情与下载 ==========\n"
        "输入 GSE 编号（如 GSE12345 或 12345），查看实验设计、样本与意图匹配；"
        "随后可选择是否下载 **Series Matrix（*_series_matrix.txt.gz）** 到本地。\n"
        "输入 q 并回车退出。\n",
        flush=True,
    )

    geo_entrez_client.configure_entrez(settings.entrez_email, settings.ncbi_api_key)

    while True:
        try:
            line = input("GSE 编号（q=退出）> ").strip()
        except EOFError:
            print("", flush=True)
            break
        if not line:
            continue
        if line.lower() == "q":
            break

        acc_norm = geo_entrez_client.normalize_gse_accession(line)
        if not acc_norm:
            print("无法识别：请输入形如 GSE12345 或仅数字部分。", flush=True)
            continue

        flow_info(f"交互：拉取 {acc_norm}")
        try:
            fr = _fetch_and_probe(acc_norm)
        except Exception as e:
            print(f"拉取失败：{e}", file=sys.stderr, flush=True)
            continue
        if fr is None:
            print(f"未在 GEO（gds）中找到：{acc_norm}。请检查编号或稍后再试。", flush=True)
            continue

        user_prompt = build_gse_detail_user_prompt(
            user_intent,
            gds_term_from_search,
            fr.record,
            fr.raw_summary,
        )
        try:
            analysis = chat_completion(
                settings,
                SYSTEM_GSE_DETAIL_ZH,
                user_prompt,
                temperature=0.3,
                flow_stage=f"LLM：GSE 详情解读 {acc_norm}",
            )
        except Exception as e:
            print(f"LLM 调用失败：{e}", file=sys.stderr, flush=True)
            continue

        print("\n" + "=" * 72, flush=True)
        print(analysis.strip(), flush=True)
        print("=" * 72 + "\n", flush=True)

        while True:
            try:
                yn = input(
                    f"是否下载 Series Matrix（{acc_norm}_series_matrix.txt.gz）到 "
                    f"{root.resolve()}/{acc_norm}/ ? [y/N] "
                ).strip().lower()
            except EOFError:
                yn = "n"
                break
            if yn in ("", "n", "no"):
                print("已跳过下载。\n", flush=True)
                break
            if yn in ("y", "yes"):
                try:
                    saved = _download_series_matrix(acc_norm, root)
                    print(f"已保存：{saved.resolve()}\n", flush=True)
                except Exception as e:
                    print(f"下载失败：{e}", file=sys.stderr, flush=True)
                break
            print("请输入 y 或 n（直接回车视为 n）。", flush=True)

    print("已退出 GSE 交互。", flush=True)
