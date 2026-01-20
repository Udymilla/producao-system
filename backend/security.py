from fastapi import Request, HTTPException, status
from fastapi.responses import RedirectResponse
from functools import wraps

# =========================
# Funções base
# =========================

def _require_login(request: Request):
    if not request.session.get("usuario_id"):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Usuário não autenticado"
        )

def _require_admin(request: Request):
    _require_login(request)

    if request.session.get("perfil") != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Acesso restrito à administração"
        )

# =========================
# Decorators
# =========================

def login_required(func):
    @wraps(func)
    async def wrapper(*args, **kwargs):
        request: Request = kwargs.get("request") or args[0]

        if not request.session.get("usuario_id"):
            # ✅ rota correta
            return RedirectResponse("/login", status_code=303)

        return await func(*args, **kwargs)
    return wrapper


def admin_required(func):
    @wraps(func)
    async def wrapper(*args, **kwargs):
        request: Request = kwargs.get("request") or args[0]

        if not request.session.get("usuario_id"):
            return RedirectResponse("/login", status_code=303)

        if request.session.get("perfil") != "admin":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Acesso restrito à administração"
            )

        return await func(*args, **kwargs)

    return wrapper
