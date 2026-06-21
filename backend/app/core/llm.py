"""LLM provider abstraction: Groq (primary) -> Ollama (fallback).

Usage:
    result = chat_json(system_prompt, user_prompt, ResponseSchema)
    # Returns a validated ResponseSchema instance.
"""
import json
import logging

from openai import OpenAI
from pydantic import BaseModel

from app.core.config import get_settings

logger = logging.getLogger(__name__)


def _groq_client() -> OpenAI:
    s = get_settings()
    return OpenAI(api_key=s.groq_api_key, base_url="https://api.groq.com/openai/v1")


def _ollama_client() -> OpenAI:
    s = get_settings()
    return OpenAI(api_key="ollama", base_url=s.ollama_base_url)


def chat_json[T: BaseModel](system: str, user: str, schema: type[T]) -> T:
    """Call the LLM in JSON mode and validate the response against `schema`.

    Tries the configured primary provider first; falls back to the other on
    any exception (network error, rate limit, key missing, etc.).
    """
    s = get_settings()
    json_schema = schema.model_json_schema()

    providers = (
        (_groq_client, s.groq_model)
        if s.llm_provider == "groq"
        else (_ollama_client, s.ollama_model)
    )
    fallback = (
        (_ollama_client, s.ollama_model)
        if s.llm_provider == "groq"
        else (_groq_client, s.groq_model)
    )

    system_with_schema = (
        f"{system}\n\nRespond ONLY with valid JSON matching this schema:\n"
        f"{json.dumps(json_schema, indent=2)}"
    )

    for client_factory, model in [providers, fallback]:
        try:
            client = client_factory()
            resp = client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": system_with_schema},
                    {"role": "user", "content": user},
                ],
                response_format={"type": "json_object"},
                temperature=0,
            )
            raw = resp.choices[0].message.content
            return schema.model_validate_json(raw)
        except Exception as e:  # noqa: BLE001
            logger.warning("LLM provider %s/%s failed: %s — trying fallback", client_factory.__name__, model, e)

    raise RuntimeError("Both LLM providers failed. Check GROQ_API_KEY and Ollama status.")
