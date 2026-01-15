from fastapi import APIRouter, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from backend.utils import templates
from backend.database import SessionLocal
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


@router.post("/login", response_class=HTMLResponse)
async def login_post(
    request: Request,
    usuario: str = Form(...),
    senha: str = Form(...)
):
    db = SessionLocal()
    user = db.query(Usuario).filter_by(nome=usuario, senha=senha).first()
    db.close()

    if not user:
        return templates.TemplateResponse(
            "login.html",
            {"request": request, "erro": True}
        )

    # cria sessão
    request.session["usuario"] = user.nome
    request.session["perfil"] = user.perfil

    return RedirectResponse(
        url="/dashboard",
        status_code=303
    )


# ======================================================
# LOGOUT
# ======================================================

@router.get("/logout")
async def logout(request: Request):
    request.session.clear()
    return RedirectResponse(
        url="/login",
        status_code=303
    )


# ======================================================
# LOGIN OPERADOR (tabela UsuarioOperacional)
# ======================================================

@router.get("/login_operador", response_class=HTMLResponse)
async def login_operador_page(request: Request):
    return templates.TemplateResponse(
        "login_operador.html",
        {"request": request, "erro": False}
    )


@router.post("/login_operador", response_class=HTMLResponse)
async def login_operador_post(
    request: Request,
    nome: str = Form(...),
    senha: str = Form(...)
):
    db = SessionLocal()
    operador = db.query(UsuarioOperacional).filter_by(
        nome=nome,
        senha=senha
    ).first()
    db.close()

    if not operador:
        return templates.TemplateResponse(
            "login_operador.html",
            {"request": request, "erro": True}
        )

    # cria sessão como operador
    request.session["usuario"] = operador.nome
    request.session["perfil"] = "operador"

    return RedirectResponse(
        url="/dashboard",
        status_code=303
    )
