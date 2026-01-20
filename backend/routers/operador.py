from fastapi import APIRouter, Request, Form, Depends, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
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
from datetime import datetime

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
async def lancar_page(request: Request, db: Session = Depends(get_db)):

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


@router.post("/lancar", response_class=HTMLResponse)
@login_required
async def lancar_post(
    request: Request,
    db: Session = Depends(get_db)
):
    form = await request.form()

    operador = form.get("operador")
    modelo = form.get("modelo")  # VEM DO SELECT
    funcao = form.get("funcao")
    quantidade = int(form.get("quantidade"))

    nova = Producao(
        operador=operador,
        modelo=modelo,
        servico=funcao,
        quantidade=quantidade,
        valor=0.0,
    )

    db.add(nova)
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
# CONSULTAR PRODUÇÃO
# ======================================================

@router.get("/consultar_producao", response_class=HTMLResponse)
@login_required
async def consultar_producao_page(request: Request, db: Session = Depends(get_db)):

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
            Ficha.modelo.label("modelo"),
            func.sum(Producao.quantidade).label("total_pecas"),
            func.sum(Producao.valor).label("valor_total"),
            func.array_agg(Ficha.numero_ficha).label("fichas")
        )
        .join(Ficha, Producao.ficha_id == Ficha.id)
        .join(UsuarioOperacional, UsuarioOperacional.id == Producao.usuario_id)
    )

    # 🔍 operador
    if operador:
        query = query.filter(
            UsuarioOperacional.nome.ilike(f"%{operador}%")
        )

    # 📅 datas (conversão correta)
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

    if not resultados:
        return {"modelos": []}

    return {
        "modelos": [r.modelo for r in resultados],
        "quantidades": [int(r.total_pecas or 0) for r in resultados],
        "valores": [float(r.valor_total or 0) for r in resultados],
        "fichas": [r.fichas[0] if r.fichas else "-" for r in resultados]
    }

@router.get("/responder_ficha", response_class=HTMLResponse)
async def responder_ficha(
    request: Request,
    token: str,
    db: Session = Depends(get_db)
):
    # 1️⃣ Busca ficha pelo token
    ficha = (
        db.query(Ficha)
        .filter(Ficha.token_qr == token)
        .first()
    )

    if not ficha:
        return HTMLResponse("Ficha não encontrada", status_code=404)

    # 2️⃣ Garante que o formulário existe
    formulario = ficha.formulario
    if not formulario:
        return HTMLResponse("Formulário não vinculado à ficha", status_code=500)

    # 3️⃣ Busca valores vinculados ao modelo
    valores = (
        db.query(ValorModelo)
        .filter(ValorModelo.modelo_id == formulario.id)
        .all()
    )

    # 4️⃣ Agrupa funções únicas
    funcoes = sorted(set(v.funcao for v in valores))

    # 5️⃣ Operadores ativos
    operadores = (
        db.query(UsuarioOperacional)
        .filter(UsuarioOperacional.ativo == 1)
        .order_by(UsuarioOperacional.nome.asc())
        .all()
    )

    return templates.TemplateResponse(
        "responder_ficha.html",
        {
            "request": request,
            "ficha": ficha,
            "formulario": formulario,
            "funcoes": funcoes,
            "valores": valores,
            "operadores": operadores
        }
    )

@router.post("/responder_ficha")
async def responder_ficha_post(
    ficha_id: int = Form(...),
    operador: str = Form(...),
    quantidade: int = Form(...),
    db: Session = Depends(get_db)
):
    ficha = db.query(Ficha).filter(Ficha.id == ficha_id).first()

    if not ficha:
        raise HTTPException(status_code=404, detail="Ficha não encontrada")

    producao = Producao(
        ficha_id=ficha.id,
        operador=operador,
        modelo=ficha.modelo,
        servico=ficha.funcao,
        quantidade=quantidade,
        valor=0,  # depois podemos calcular automático
        criado_em=datetime.utcnow()
    )

    db.add(producao)
    db.commit()

    return RedirectResponse(
        url="/dashboard",
        status_code=303
    )

