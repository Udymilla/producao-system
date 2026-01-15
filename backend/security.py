from fastapi import Request, HTTPException, status
from functools import wraps

# =========================
# Funções base
# =========================

def _require_login(request: Request):
    if "usuario" not in request.session:
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
        request: Request = kwargs.get("request")
        if not request:
            raise RuntimeError("Request não encontrado na rota")

        _require_login(request)
        return await func(*args, **kwargs)

    return wrapper


def admin_required(func):
    @wraps(func)
    async def wrapper(*args, **kwargs):
        request: Request = kwargs.get("request")
        if not request:
            raise RuntimeError("Request não encontrado na rota")

        _require_admin(request)
        return await func(*args, **kwargs)

    return wrapper
