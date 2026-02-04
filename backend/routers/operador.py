from fastapi import APIRouter, Request, Form, Depends, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.orm import Session
from sqlalchemy import func, and_
from datetime import datetime

from backend.utils import templates
from backend.database import get_db
from backend.security import login_required
from backend.models import (
    Producao,
    Ficha,
    Formulario,
    ValorModelo,
    UsuarioOperacional,
    Funcao
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

@router.get("/lancar")
async def lancar_producao(
    request: Request,
    db: Session = Depends(get_db)
):
    # 👤 Operadores
    operadores = (
        db.query(UsuarioOperacional)
        .filter(UsuarioOperacional.ativo == 1)
        .order_by(UsuarioOperacional.nome)
        .all()
    )

    # 📦 MODELOS (EXATAMENTE IGUAL AO gerar_fichas)
    modelos = (
        db.query(Formulario)
        .filter(Formulario.ativo == True)
        .order_by(Formulario.nome_modelo.asc())
        .all()
    )

    # 🧩 Funções (variável, como você explicou)
    funcoes = (
        db.query(Funcao)
        .order_by(Funcao.nome)
        .all()
    )

    # DEBUG
    print("OPERADORES:", [(o.id, o.nome) for o in operadores])
    print("MODELOS:", [(m.id, m.nome_modelo) for m in modelos])
    print("FUNCOES:", [(f.id, f.nome) for f in funcoes])

    return templates.TemplateResponse(
        "lancar.html",
        {
            "request": request,
            "operadores": operadores,
            "modelos": modelos,
            "funcoes": funcoes
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
#@login_required
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
async def consultar_producao_dados(
    operador: str = Form(...),
    data_inicial: str = Form(None),
    data_final: str = Form(None),
    db: Session = Depends(get_db)
):
    # ============================
    # QUERY COM VALOR
    # ============================
    query = (
        db.query(
            Formulario.nome_modelo.label("modelo"),
            Funcao.nome.label("funcao"),
            func.sum(Producao.quantidade).label("total_pecas"),
            ValorModelo.valor.label("valor_unitario"),
            (
                func.sum(Producao.quantidade) * ValorModelo.valor
            ).label("valor_total")
        )
        .join(Ficha, Ficha.id == Producao.ficha_id)
        .join(Formulario, Formulario.id == Ficha.formulario_id)
        .join(Funcao, Funcao.id == Producao.funcao_id)
        .join(
            ValorModelo,
            and_(
                ValorModelo.modelo_id == Formulario.id,
                ValorModelo.funcao_id == Funcao.id
            )
        )
        .filter(Producao.operador == operador)
        .group_by(
            Formulario.nome_modelo,
            Funcao.nome,
            ValorModelo.valor
        )
        .order_by(Formulario.nome_modelo, Funcao.nome)
    )

    # ============================
    # FILTROS DE DATA (opcional)
    # ============================
    if data_inicial:
        query = query.filter(
            Producao.criado_em >= datetime.fromisoformat(data_inicial)
        )

    if data_final:
        query = query.filter(
            Producao.criado_em <= datetime.fromisoformat(data_final)
        )

    resultados = query.all()

    if not resultados:
        return {"erro": True}

    # ============================
    # RETORNO PARA O FRONT
    # ============================
    return {
        "modelos": [r.modelo for r in resultados],
        "funcoes": [r.funcao for r in resultados],
        "quantidades": [int(r.total_pecas) for r in resultados],
        "valores_unitarios": [float(r.valor_unitario) for r in resultados],
        "valores_totais": [float(r.valor_total) for r in resultados],
    }

@router.post("/consultar_fichas_dados")
#@login_required
async def consultar_fichas_dados(
    numero_ficha: str = Form(None),
    modelo: str = Form(None),
    db: Session = Depends(get_db)
):
    query = (
        db.query(
            Ficha.numero_ficha.label("numero_ficha"),
            Formulario.nome_modelo.label("modelo"),
            Ficha.quantidade_total.label("quantidade_ficha"),
            Producao.operador.label("operador"),
            Funcao.nome.label("funcao")
        )
        .join(Ficha.formulario)
        .outerjoin(Producao, Producao.ficha_id == Ficha.id)
        .outerjoin(Funcao, Funcao.id == Producao.funcao_id)
        .order_by(Ficha.numero_ficha)
    )

    if numero_ficha:
        query = query.filter(Ficha.numero_ficha == numero_ficha)

    if modelo:
        query = query.filter(Formulario.nome_modelo.ilike(f"%{modelo}%"))

    resultados = query.all()

    return {
        "dados": [
            {
                "numero_ficha": r.numero_ficha,
                "modelo": r.modelo,
                "quantidade_ficha": int(r.quantidade_ficha),
                "operador": r.operador or "-",
                "funcao": r.funcao or "-",
                "status": "CONCLUÍDA" if r.operador else "EM ANDAMENTO"
            }
            for r in resultados
        ]
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

    # 🔑 BUSCA SOMENTE FUNÇÕES RELACIONADAS AO MODELO
    funcoes = (
        db.query(Funcao)
        .join(ValorModelo, ValorModelo.funcao_id == Funcao.id)
        .filter(ValorModelo.modelo_id == ficha.formulario_id)
        .order_by(Funcao.nome.asc())
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
    funcao_id: str = Form(...),
    db: Session = Depends(get_db)
):
    
    print("FORM DATA:", ficha_id, operador, funcao_id)
    ficha = db.query(Ficha).filter(Ficha.id == ficha_id).first()

    if not ficha:
        raise HTTPException(status_code=404, detail="Ficha não encontrada")

    producao = Producao(
    ficha_id=ficha.id,
    operador=operador,
    funcao_id=funcao_id,
    quantidade=ficha.quantidade_total,
    criado_em=datetime.utcnow()
)
    db.add(producao)
    db.commit()

    return RedirectResponse("/dashboard", status_code=303)

    print("ficha_id:", ficha_id)
    print("operador:", operador)
    print("funcao_id:", funcao_id)
    print("quantidade herdada:", ficha.quantidade_total)