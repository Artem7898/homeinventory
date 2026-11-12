"""Authentication policy helpers: forwarded IP headers are untrusted by default."""


def client_ip(request):
    """Use the socket peer; configure a trusted edge limiter for proxy deployments."""
    return request.META.get('REMOTE_ADDR')
