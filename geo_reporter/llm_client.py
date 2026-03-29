"""OpenAI 兼容 Chat Completions 客户端。"""

from __future__ import annotations

from openai import OpenAI

from geo_reporter.config import Settings


def get_client(settings: Settings) -> OpenAI:
    kwargs: dict = {"api_key": settings.openai_api_key}
    if settings.openai_base_url:
        kwargs["base_url"] = settings.openai_base_url
    return OpenAI(**kwargs)


def chat_completion(
    settings: Settings,
    system_prompt: str,
    user_prompt: str,
    temperature: float = 0.4,
    *,
    flow_stage: str | None = None,
) -> str:
    if flow_stage:
        from geo_reporter.flow_log import flow_info

        flow_info(f"开始 | {flow_stage}")

    client = get_client(settings)
    try:
        resp = client.chat.completions.create(
            model=settings.openai_model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=temperature,
        )
    except Exception:
        if flow_stage:
            from geo_reporter.flow_log import flow_info

            flow_info(f"失败 | {flow_stage}")
        raise

    choice = resp.choices[0]
    content = choice.message.content
    out = "" if not content else content.strip()

    if flow_stage:
        from geo_reporter.flow_log import flow_info

        flow_info(f"完成 | {flow_stage}")
    return out
