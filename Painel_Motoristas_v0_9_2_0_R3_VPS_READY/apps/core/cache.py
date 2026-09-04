from __future__ import annotations

import logging
from django.core.cache import cache

logger = logging.getLogger("apps.cache")
VERSION_KEY = "painel:operational-cache-version"


def cache_version() -> int:
    value = cache.get(VERSION_KEY)
    if value is None:
        # set/add funciona tanto no LocMem quanto no RedisCache.
        cache.add(VERSION_KEY, 1, timeout=None)
        value = cache.get(VERSION_KEY, 1)
    try:
        return int(value)
    except (TypeError, ValueError):
        cache.set(VERSION_KEY, 1, timeout=None)
        return 1


def versioned_key(namespace: str, *parts) -> str:
    safe = ":".join(str(p).replace(" ", "_") for p in parts)
    return f"painel:v{cache_version()}:{namespace}:{safe}"


def invalidate_operational_cache(reason: str = "unspecified") -> int:
    """Invalidação centralizada para qualquer fato que altera leitura operacional.

    Em vez de varrer chaves Redis, incrementa um namespace. Chaves antigas
    expiram naturalmente e nenhuma request seguinte reutiliza fotografia velha.
    """
    try:
        value = cache.incr(VERSION_KEY)
    except ValueError:
        cache.set(VERSION_KEY, 2, timeout=None)
        value = 2
    # Contexto de cabeçalho não usa namespace versionado, portanto precisa ser
    # limpo explicitamente para refletir imediatamente uma importação concluída.
    cache.delete("context:last_ssw_sync")
    logger.info("CACHE invalidated version=%s reason=%s", value, reason)
    return int(value)
