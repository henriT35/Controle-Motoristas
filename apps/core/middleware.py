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
