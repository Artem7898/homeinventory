from functools import wraps

from django_ratelimit.decorators import ratelimit


def secure_admin_login(view_func):
    """Защита админки от брутфорса"""
    @ratelimit(
        key='ip',
        rate='5/m',  # 5 попыток с одного IP в минуту
        method=['POST'],
        block=True
    )
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        return view_func(request, *args, **kwargs)

    return wrapper