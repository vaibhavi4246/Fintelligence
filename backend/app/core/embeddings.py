"""Embedding provider abstraction: bge-base (local, 768-dim) -> OpenAI fallback.

Returns 768-dim vectors to match chunks.embedding vector(768) in the DB schema.
"""
import logging
from functools import lru_cache

from app.core.config import get_settings

logger = logging.getLogger(__name__)

_BATCH_SIZE = 100


@lru_cache(maxsize=1)
def _load_bge_model():
    from sentence_transformers import SentenceTransformer
    return SentenceTransformer(get_settings().embedding_model)


def embed_texts(texts: list[str]) -> list[list[float]]:
    """Return 768-dim embeddings for each text, batching at 100.

    Provider order: bge-base-en-v1.5 (local) -> text-embedding-3-small (OpenAI, dim=768).
    """
    s = get_settings()
    results: list[list[float]] = []

    for i in range(0, len(texts), _BATCH_SIZE):
        batch = texts[i : i + _BATCH_SIZE]

        if s.embedding_provider == "bge":
            try:
                model = _load_bge_model()
                vecs = model.encode(batch, normalize_embeddings=True).tolist()
                results.extend(vecs)
                continue
            except Exception as e:  # noqa: BLE001
                logger.warning("bge embedding failed: %s — falling back to OpenAI", e)

        # OpenAI fallback (or primary when embedding_provider=openai)
        from openai import OpenAI
        client = OpenAI(api_key=s.openai_api_key)
        resp = client.embeddings.create(
            model="text-embedding-3-small",
            input=batch,
            dimensions=s.embedding_dim,
        )
        vecs = [item.embedding for item in sorted(resp.data, key=lambda x: x.index)]
        results.extend(vecs)

    return results
