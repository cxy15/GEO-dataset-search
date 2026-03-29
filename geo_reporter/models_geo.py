"""GEO 记录与检索结果数据结构。"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class GeoSeriesRecord:
    """单条 GEO Series（来自 Entrez gds esummary）。"""

    gds_id: str
    accession: str
    title: str
    summary: str
    taxon: str
    gpl: str
    n_samples: int
    gds_type: str
    ptech_type: str
    pubmed_ids: str
    ftp_link: str
    availability_tier: str = "unknown"
    availability_notes: str = ""
    probe_matrix_url: str | None = None
    probe_matrix_status: str | None = None
    probe_matrix_size: int | None = None
    probe_soft_url: str | None = None
    probe_soft_status: str | None = None
    probe_soft_size: int | None = None
    probe_gpl_url: str | None = None
    probe_gpl_status: str | None = None

    def to_llm_text(self) -> str:
        lines = [
            f"Accession: {self.accession}",
            f"标题: {self.title}",
            f"物种: {self.taxon}",
            f"平台 GPL: {self.gpl}",
            f"样本数: {self.n_samples}",
            f"类型: {self.gds_type}",
            f"可用性分级: {self.availability_tier}",
            f"可用性说明: {self.availability_notes or '（无）'}",
            "",
            "摘要:",
            (self.summary.strip() if self.summary else "（无）")[:4000],
        ]
        return "\n".join(lines)


@dataclass
class GeoSearchResult:
    """一次 gds 检索结果。"""

    query: str
    total_count: int
    retrieved_ids: list[str]
    records: list[GeoSeriesRecord] = field(default_factory=list)


@dataclass
class DatasetRelevance:
    """单条数据集相对用户研究意图的相关性。"""

    accession: str
    level: str
    weight: float
    rationale: str


@dataclass(frozen=True)
class GeoSearchRunOutcome:
    """主检索流水线结束后的结果（供 GSE 交互等环节复用检索意图与检索式）。"""

    report_path: Path
    gds_term: str
    user_intent: str


@dataclass
class GseFetchResult:
    """单次按 Accession 拉取的 gds esummary。"""

    record: GeoSeriesRecord
    raw_summary: dict
