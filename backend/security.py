from fastapi import Request
from fastapi.responses import RedirectResponse
from functools import wraps

# ===============================
# LOGIN REQUIRED (QUALQUER USUÁRIO)
# ===============================
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

        # 🔥 AQUI ESTAVA O ERRO
        if not request.session.get("usuario_id"):
            return RedirectResponse("/login", status_code=302)

        return await func(*args, **kwargs)

    return wrapper
# ===============================
# ADMIN REQUIRED
# ===============================
def admin_required(func):
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

        # não logado
        if not request.session.get("usuario_id"):
            return RedirectResponse("/login", status_code=302)

        # não é admin
        if request.session.get("perfil") != "admin":
            return RedirectResponse("/dashboard", status_code=302)

        return await func(*args, **kwargs)

    return wrapper
