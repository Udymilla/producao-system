from fastapi import APIRouter, Request, Form, Depends, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.orm import Session
from sqlalchemy import func
from datetime import datetime

from backend.utils import templates
from backend.database import get_db
from backend.security import login_required
from backend.models import (
    Producao,
    Ficha,
    Formulario,
    ValorModelo,
    UsuarioOperacional
)

router = APIRouter()

# ======================================================
# DASHBOARD
# ======================================================

@router.get("/dashboard", response_class=HTMLResponse)
#@login_required
async def dashboard(request: Request):
    return templates.TemplateResponse(
        "dashboard.html",
        {"request": request}
    )

# ======================================================
# LANÇAR PRODUÇÃO (TELA)
# ======================================================

@router.get("/lancar", response_class=HTMLResponse)
@login_required
async def lancar_page(
    request: Request,
    db: Session = Depends(get_db)
):
    modelos = (
        db.query(Formulario)
        .filter(Formulario.ativo == True)
        .order_by(Formulario.nome_modelo.asc())
        .all()
    )

    return templates.TemplateResponse(
        "lancar.html",
        {
            "request": request,
            "modelos": modelos
        }

    

    )

# ======================================================
# LANÇAR PRODUÇÃO (POST)
# ======================================================

@router.post("/lancar", response_class=HTMLResponse)
@login_required
async def lancar_post(
    request: Request,
    db: Session = Depends(get_db)
):
    form = await request.form()

    operador = form.get("operador")
    modelo = form.get("modelo")
    funcao = form.get("funcao")
    quantidade = int(form.get("quantidade"))

    producao = Producao(
        operador=operador,
        modelo=modelo,
        servico=funcao,
        quantidade=quantidade,
        valor=0.0,
        criado_em=datetime.utcnow()
    )

    db.add(producao)
    db.commit()

    return templates.TemplateResponse(
        "pagina.html",
        {
            "request": request,
            "titulo": "Produção lançada ✅",
            "mensagem": f"{quantidade} peças do modelo {modelo} lançadas para {operador}"
        }
    )

# ======================================================
# CONSULTAR FICHAS
# ======================================================

@router.get("/consultar_fichas", response_class=HTMLResponse)
@login_required
async def consultar_fichas_page(request: Request):
    return templates.TemplateResponse(
        "consultar_fichas.html",
        {"request": request}
    )

# ======================================================
# CONSULTAR PRODUÇÃO (TELA)
# ======================================================

@router.get("/consultar_producao", response_class=HTMLResponse)
@login_required
async def consultar_producao_page(
    request: Request,
    db: Session = Depends(get_db)
):
    operadores = (
        db.query(UsuarioOperacional.nome)
        .distinct()
        .order_by(UsuarioOperacional.nome.asc())
        .all()
    )

    modelos = (
        db.query(Formulario.nome_modelo)
        .filter(Formulario.ativo == True)
        .order_by(Formulario.nome_modelo.asc())
        .all()
    )

    return templates.TemplateResponse(
        "consultar_producao.html",
        {
            "request": request,
            "operadores": [o[0] for o in operadores],
            "modelos": [m[0] for m in modelos],
        }
    )

# ======================================================
# CONSULTAR PRODUÇÃO (DADOS)
# ======================================================

@router.post("/consultar_producao_dados")
@login_required
def consultar_producao_dados(
    operador: str = Form(""),
    data_inicial: str = Form(""),
    data_final: str = Form(""),
    db: Session = Depends(get_db)
):
    query = (
        db.query(
            Ficha.modelo.label("modelo"),
            func.sum(Producao.quantidade).label("total_pecas"),
            func.sum(Producao.valor).label("valor_total")
        )
        .join(Ficha, Producao.ficha_id == Ficha.id)
    )

    if operador:
        query = query.filter(Producao.operador.ilike(f"%{operador}%"))

    if data_inicial:
        query = query.filter(
            Producao.criado_em >= datetime.fromisoformat(data_inicial)
        )

    if data_final:
        query = query.filter(
            Producao.criado_em <= datetime.fromisoformat(data_final)
        )

    query = query.group_by(Ficha.modelo)

    resultados = query.all()

    return {
        "modelos": [r.modelo for r in resultados],
        "quantidades": [int(r.total_pecas or 0) for r in resultados],
        "valores": [float(r.valor_total or 0) for r in resultados],
    }

# ======================================================
# RESPONDER FICHA (QR CODE)
# ======================================================

@router.get("/responder_ficha", response_class=HTMLResponse)
async def responder_ficha(
    request: Request,
    token: str,
    db: Session = Depends(get_db)
):
    ficha = (
        db.query(Ficha)
        .filter(Ficha.token_qr == token)
        .first()
    )

    if not ficha:
        raise HTTPException(status_code=404, detail="Ficha não encontrada")

    formulario = ficha.formulario

    funcoes = (
        db.query(ValorModelo)
        .filter(ValorModelo.modelo_id == formulario.id)
        .order_by(ValorModelo.funcao.asc())
        .all()
    )

    return templates.TemplateResponse(
        "responder_ficha.html",
        {
            "request": request,
            "ficha": ficha,
            "formulario": formulario,
            "funcoes": funcoes
        }
    )

# ======================================================
# RESPONDER FICHA (POST)
# ======================================================

@router.post("/responder_ficha")
async def responder_ficha_post(
    ficha_id: int = Form(...),
    operador: str = Form(...),
    funcao: str = Form(...),
    db: Session = Depends(get_db)
):
    ficha = db.query(Ficha).filter(Ficha.id == ficha_id).first()

    if not ficha:
        raise HTTPException(status_code=404, detail="Ficha não encontrada")

    producao = Producao(
        ficha_id=ficha.id,
        operador=operador,
        modelo=ficha.formulario.nome_modelo,
        servico=funcao,
        quantidade=ficha.quantidade_total,
        valor=0.0,
        criado_em=datetime.utcnow()
    )

    db.add(producao)
    db.commit()

    return RedirectResponse("/dashboard", status_code=303)

