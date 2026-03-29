"""从环境变量加载配置（与 PubMed 项目对齐）。"""

from __future__ import annotations

import os
from dataclasses import dataclass

from dotenv import load_dotenv

load_dotenv()


@dataclass(frozen=True)
class Settings:
    entrez_email: str
    ncbi_api_key: str | None
    openai_api_key: str
    openai_base_url: str | None
    openai_model: str


def load_settings() -> Settings:
    email = os.getenv("ENTREZ_EMAIL", "").strip()
    ncbi_key = (
        os.getenv("NCBI_API_KEY", "").strip()
        or os.getenv("ENTREZ_API_KEY", "").strip()
        or None
    )
    api_key = os.getenv("OPENAI_API_KEY", "").strip()
    base = os.getenv("OPENAI_BASE_URL", "").strip() or None
    model = os.getenv("OPENAI_MODEL", "gpt-4o-mini").strip()

    return Settings(
        entrez_email=email,
        ncbi_api_key=ncbi_key,
        openai_api_key=api_key,
        openai_base_url=base,
        openai_model=model,
    )
