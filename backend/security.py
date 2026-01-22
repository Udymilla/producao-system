from fastapi import Request
from fastapi.responses import RedirectResponse
from functools import wraps

def login_required(func):
    @wraps(func)
    async def wrapper(*args, **kwargs):
        request: Request = kwargs.get("request")

        if not request:
            for arg in args:
                if isinstance(arg, Request):
                    request = arg
                    break

        if not request:
            return RedirectResponse("/login", status_code=302)

        if not request.session.get("user_id"):
            return RedirectResponse("/login", status_code=302)

        return await func(*args, **kwargs)

    return wrapper
