from fastapi import APIRouter, Request, Form, Depends
from fastapi.responses import HTMLResponse, RedirectResponse
from backend.utils import templates
from sqlalchemy import func, or_
from sqlalchemy.orm import Session
from backend.database import SessionLocal, get_db
from backend.models import Usuario, UsuarioOperacional

# ======================================================
# CONFIG
# ======================================================

router = APIRouter()


# ======================================================
# LOGIN ADMIN / USUÁRIO PADRÃO
# ======================================================

@router.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    return templates.TemplateResponse(
        "login.html",
        {"request": request, "erro": False}
    )


@router.post("/login")
async def login_post(
    request: Request,
    usuario: str = Form(...),
    senha: str = Form(...),
    db: Session = Depends(get_db)
):
    user = (
        db.query(Usuario)
        .filter(Usuario.nome == usuario.upper())
        .filter(Usuario.senha == senha)
        .first()
    )

    if not user:
        return templates.TemplateResponse(
            "login.html",
            {"request": request, "erro": "Usuário ou senha inválidos"}
        )

    # 🔐 SESSÃO CORRETA
    request.session["usuario_id"] = user.id
    request.session["usuario"] = user.nome
    request.session["perfil"] = user.perfil

    return RedirectResponse("/dashboard", status_code=303)
