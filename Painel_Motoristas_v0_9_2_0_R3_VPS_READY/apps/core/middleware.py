class ContentSecurityPolicyMiddleware:
    """CSP compatível com os CDNs usados pelos mockups web.

    Fontes/JS externos são mantidos porque o projeto não distribui arquivos de fonte.
    """
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        response.setdefault(
            "Content-Security-Policy",
            "default-src 'self'; "
            "script-src 'self' 'unsafe-inline' https://unpkg.com https://cdn.jsdelivr.net; "
            "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
            "font-src 'self' https://fonts.gstatic.com data:; "
            "img-src 'self' data: blob:; connect-src 'self' https://raw.githubusercontent.com https://servicodados.ibge.gov.br; frame-ancestors 'none';"
        )
        return response


class ScreenPerformanceMiddleware:
    """Mede telas operacionais críticas sem modificar seu fluxo."""
    PREFIXES = {
        "/operacao/hoje/": "operation.today",
        "/operacao/entregas/": "deliveries",
        "/motoristas/avaliacoes/": "quality.reviews",
        "/motoristas/": "drivers",
        "/portal/motorista/": "portal",
        "/comprovantes/": "proofs",
        "/whatsapp/": "whatsapp",
        "/dashboard/": "dashboard.request",
    }

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        import logging
        import time
        from django.conf import settings
        from django.db import connection

        label = next((name for prefix, name in self.PREFIXES.items() if request.path.startswith(prefix)), None)
        if not label:
            return self.get_response(request)
        started = time.perf_counter()
        logger = logging.getLogger("apps.performance")
        query_stats = {"count": 0, "seconds": 0.0}

        def sql_timer(execute, sql, params, many, context):
            sql_started = time.perf_counter()
            try:
                return execute(sql, params, many, context)
            finally:
                query_stats["count"] += 1
                query_stats["seconds"] += time.perf_counter() - sql_started

        try:
            if getattr(settings, "PERF_SQL_LOG", False):
                with connection.execute_wrapper(sql_timer):
                    return self.get_response(request)
            return self.get_response(request)
        finally:
            total = time.perf_counter() - started
            logger.info("PERF %s.total = %.3fs", label, total)
            if getattr(settings, "PERF_SQL_LOG", False):
                logger.info(
                    "PERF %s.sql queries=%s time=%.3fs python_template=%.3fs",
                    label, query_stats["count"], query_stats["seconds"], max(total-query_stats["seconds"], 0),
                )
