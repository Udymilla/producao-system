from fastapi import APIRouter, Request, Form, Depends
from fastapi.responses import HTMLResponse
from backend.utils import templates
from sqlalchemy.orm import Session
from sqlalchemy import func
from backend.database import SessionLocal, get_db 
from backend.models import (
    Producao,
    Ficha,
    Formulario,
    ValorModelo,
    UsuarioOperacional
)
from backend.security import login_required
from typing import Optional

# ======================================================
# CONFIG
# ======================================================

router = APIRouter()

# ======================================================
# DASHBOARD
# ======================================================

@router.get("/dashboard", response_class=HTMLResponse)
@login_required
async def dashboard(request: Request):
    return templates.TemplateResponse(
        "dashboard.html",
        {"request": request}
    )

# ======================================================
# LANÇAR PRODUÇÃO (HTML)
# ======================================================

@router.get("/lancar", response_class=HTMLResponse)
@login_required
async def lancar_page(request: Request):
    return templates.TemplateResponse(
        "lancar.html",
        {"request": request}
    )


@router.post("/lancar", response_class=HTMLResponse)
@login_required
async def lancar_post(request: Request):
    form = await request.form()

    operador = form.get("operador")
    modelo = form.get("modelo")
    funcao = form.get("funcao")
    quantidade = int(form.get("quantidade"))
    qtd_fichas = int(form.get("qtd_fichas"))
    numero_inicial = int(form.get("numero_inicial"))

    fichas = [str(numero_inicial + i) for i in range(qtd_fichas)]

    mensagem = (
        f"<b>Operador:</b> {operador}<br>"
        f"<b>Modelo:</b> {modelo}<br>"
        f"<b>Função:</b> {funcao}<br>"
        f"<b>Qtd por ficha:</b> {quantidade}<br>"
        f"<b>Fichas geradas:</b> {', '.join(fichas)}"
    )

    return templates.TemplateResponse(
        "pagina.html",
        {
            "request": request,
            "titulo": "Lançamento Concluído ✅",
            "mensagem": mensagem
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
# CONSULTAR PRODUÇÃO
# ======================================================

@router.get("/consultar_producao", response_class=HTMLResponse)
@login_required
async def consultar_producao_page(request: Request):
    db = SessionLocal()

    operadores = (
        db.query(Producao.operador)
        .distinct()
        .order_by(Producao.operador.asc())
        .all()
    )
    modelos = (
        db.query(Producao.modelo)
        .distinct()
        .order_by(Producao.modelo.asc())
        .all()
    )

    db.close()

    return templates.TemplateResponse(
        "consultar_producao.html",
        {
            "request": request,
            "operadores": [o[0] for o in operadores],
            "modelos": [m[0] for m in modelos],
        }
    )

# ======================================================
# CONSULTAR PRODUÇÃO (DADOS AJAX)
# ======================================================

@router.post("/consultar_producao_dados")
def consultar_producao_dados(
    operador: str = Form(""),
    data_inicial: str = Form(""),
    data_final: str = Form(""),
    db: Session = Depends(get_db)
):
    query = (
        db.query(
            Producao.modelo.label("modelo"),
            func.sum(Producao.quantidade).label("total_pecas"),
            func.sum(Producao.valor).label("valor_total"),
            func.array_agg(Producao.ficha_id).label("fichas")
        )
        .join(UsuarioOperacional, UsuarioOperacional.id == Producao.usuario_id)
    )

    # 🔍 Filtro por operador (case-insensitive)
    if operador:
        query = query.filter(
            UsuarioOperacional.nome.ilike(f"%{operador}%")
        )

    # 📅 Data inicial
    if data_inicial:
        query = query.filter(Producao.criado_em >= data_inicial)

    # 📅 Data final
    if data_final:
        query = query.filter(Producao.criado_em <= data_final)

    query = query.group_by(Producao.modelo)

    resultados = query.all()

    if not resultados:
        return {"modelos": []}

    return {
        "modelos": [r.modelo for r in resultados],
        "quantidades": [int(r.total_pecas or 0) for r in resultados],
        "valores": [float(r.valor_total or 0) for r in resultados],
        "fichas": [r.fichas[0] if r.fichas else "-" for r in resultados]
    }
