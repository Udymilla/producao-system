from fastapi import APIRouter, Request, Form, Depends
from fastapi.responses import HTMLResponse
from backend.utils import templates
from sqlalchemy.orm import Session
from backend.database import SessionLocal, get_db
from backend.models import Producao, Ficha
from backend.security import login_required

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
@login_required
async def consultar_producao_dados(
    request: Request,
    operador: str = Form(...),
    data_inicial: str = Form(None),
    data_final: str = Form(None),
    db: Session = Depends(get_db)
):
    query = db.query(Producao).filter(
        Producao.operador.ilike(f"%{operador}%")
    )

    if data_inicial:
        query = query.filter(Producao.criado_em >= data_inicial)
    if data_final:
        query = query.filter(Producao.criado_em <= data_final)

    resultados = query.order_by(
        Producao.criado_em.desc()
    ).all()

    if not resultados:
        return {"erro": "Nenhum resultado encontrado."}

    modelos = []
    quantidades = []
    valores = []
    fichas = []

    for r in resultados:
        modelos.append(r.modelo)
        quantidades.append(r.quantidade)
        fichas.append(r.ficha_id)
        valores.append(r.valor or 0)

    return {
        "modelos": modelos,
        "quantidades": quantidades,
        "valores": valores,
        "fichas": fichas,
    }
