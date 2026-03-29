"""将 LLM 报告正文写入 UTF-8 文本文件。"""

from __future__ import annotations

from pathlib import Path


def normalize_report_output_path(path: Path) -> Path:
    p = Path(path).expanduser()
    if p.suffix.lower() == ".pdf":
        return p.with_suffix(".txt")
    return p


def write_report_txt(title: str, body: str, output_path: Path) -> Path:
    out = normalize_report_output_path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    title_line = title.strip() or "GEO 数据推荐报告"
    sep = "=" * min(max(len(title_line), 8), 80)
    text = f"{title_line}\n{sep}\n\n{body.strip()}\n"
    with out.open("w", encoding="utf-8", newline="\n") as f:
        f.write(text)
    return out
