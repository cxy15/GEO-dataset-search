#!/usr/bin/env python3
"""命令行入口。"""

from __future__ import annotations

import argparse
import sys
import traceback
from pathlib import Path

from geo_reporter.config import load_settings
from geo_reporter.flow_log import flow_info
from geo_reporter import modes_geo


def main() -> int:
    parser = argparse.ArgumentParser(
        description="基于 NCBI GEO（Entrez db=gds）与 OpenAI 兼容 API 的数据集检索与中文推荐报告。",
        epilog=(
            "环境变量：ENTREZ_EMAIL；可选 NCBI_API_KEY。"
            "LLM：OPENAI_API_KEY + OPENAI_BASE_URL（一般为 …/v1）。"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        default=Path("geo_report.txt"),
        help="输出 UTF-8 文本报告路径（默认 geo_report.txt）",
    )
    parser.add_argument(
        "-n",
        "--retmax",
        type=int,
        default=40,
        help="单次检索返回并拉取详情的最大条数（默认 40）",
    )
    parser.add_argument(
        "-q",
        "--raw-query",
        dest="raw_query",
        default=None,
        metavar="QUERY",
        help="跳过 LLM 翻译，直接使用此 gds 检索式",
    )
    parser.add_argument(
        "--no-probe",
        action="store_true",
        help="关闭对 NCBI GEO HTTPS 的远程文件探测（仅元数据启发式，更快）",
    )
    parser.add_argument(
        "--no-gse-session",
        action="store_true",
        help="报告完成后不进入「输入 GSE 编号查看详情与可选下载」的交互（便于脚本/管道）",
    )

    parser.add_argument(
        "intent",
        nargs="?",
        default="",
        help="研究意图的自然语言描述（中/英均可）；若使用 -q 则仍可作为报告中的需求说明",
    )

    args = parser.parse_args()
    settings = load_settings()

    if not settings.entrez_email:
        print("错误：请在环境变量 ENTREZ_EMAIL 中设置 NCBI 要求的联系邮箱。", file=sys.stderr)
        return 1
    if not settings.openai_api_key:
        print("错误：请在环境变量 OPENAI_API_KEY 中设置 API 密钥。", file=sys.stderr)
        return 1

    intent = (args.intent or "").strip()
    if not intent and not args.raw_query:
        print("错误：请提供研究意图（positional intent），或使用 --raw-query 并建议同时写清意图。", file=sys.stderr)
        return 1
    if not intent and args.raw_query:
        intent = "（用户仅提供手工检索式，未单独描述意图；请结合检索式理解需求）"

    probe_remote = not args.no_probe
    flow_info(
        f"CLI search  retmax={args.retmax}  probe_remote={probe_remote}  输出: {args.output}"
    )

    try:
        outcome = modes_geo.run_search(
            settings,
            intent,
            raw_query=args.raw_query,
            retmax=args.retmax,
            output_path=args.output,
            probe_remote=probe_remote,
        )
        if not args.no_gse_session and sys.stdin.isatty():
            from geo_reporter import gse_interactive

            gse_interactive.run_session(
                settings,
                outcome.user_intent,
                outcome.gds_term,
            )
        return 0
    except Exception:
        print(traceback.format_exc(), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
