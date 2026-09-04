from __future__ import annotations

import logging
import time
from contextlib import contextmanager

logger = logging.getLogger("apps.performance")


@contextmanager
def perf_span(name: str):
    """Loga duração real sem alterar o resultado da operação medida."""
    started = time.perf_counter()
    try:
        yield
    finally:
        elapsed = time.perf_counter() - started
        logger.info("PERF %s = %.3fs", name, elapsed)


class PerfTimer:
    """Timer simples para uma request com subtarefas nomeadas."""

    def __init__(self, prefix: str):
        self.prefix = prefix
        self.started = time.perf_counter()
        self.last = self.started

    def mark(self, component: str) -> float:
        now = time.perf_counter()
        elapsed = now - self.last
        self.last = now
        logger.info("PERF %s.%s = %.3fs", self.prefix, component, elapsed)
        return elapsed

    def total(self) -> float:
        elapsed = time.perf_counter() - self.started
        logger.info("PERF %s.total = %.3fs", self.prefix, elapsed)
        return elapsed
