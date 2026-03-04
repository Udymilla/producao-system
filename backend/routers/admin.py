from fastapi import APIRouter, Request, Form, Depends, File, UploadFile, Query, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse, FileResponse, StreamingResponse
from sqlalchemy.orm import Session
from sqlalchemy import func, literal
import os
import io
import uuid
import qrcode
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import cm
from reportlab.lib.utils import ImageReader
from backend.database import SessionLocal, get_db
from backend.models import Usuario, Formulario, ValorModelo, Ficha, Funcao, Producao, UsuarioOperacional
from backend.security import admin_required
from backend.utils import templates
from datetime import datetime, timedelta
import io
from fastapi.responses import StreamingResponse

# ======================================================
# CONFIG
# ======================================================

router = APIRouter()

UPLOAD_DIR = "backend/frontend/static/uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)

# ======================================================
# ADMIN DASHBOARD
# ======================================================

@router.get("/administracao", response_class=HTMLResponse)
@admin_required
async def administracao_page(request: Request):
    return templates.TemplateResponse(
        "administracao.html",
        {"request": request}
    )

# ======================================================
# USUÁRIOS
# ======================================================

@router.get("/cadastrar_usuario", response_class=HTMLResponse)
@admin_required
async def cadastrar_usuario_page(request: Request):
    return templates.TemplateResponse(
        "cadastrar_usuario.html",
        {"request": request}
    )

@router.post("/cadastrar_usuario", response_class=HTMLResponse)
@admin_required
async def cadastro_formulario_post(
    request: Request,
    nome: str = Form(...),
    senha: str = Form(...),
    perfil: str = Form(...),
    db: Session = Depends(get_db)
):

    db = SessionLocal()

    existente = db.query(Usuario).filter(Usuario.nome == nome).first()
    if existente:
        db.close()
        return templates.TemplateResponse(
            "cadastrar_usuario.html",
            {
                "request": request,
                "mensagem": f"⚠️ O usuário <b>{nome}</b> já existe!"
            }
        )

    novo = Usuario(nome=nome, senha=senha, perfil=perfil)
    db.add(novo)
    db.commit()
    db.close()

    return templates.TemplateResponse(
        "cadastrar_usuario.html",
        {
            "request": request,
            "mensagem": f"✅ Usuário <b>{nome}</b> cadastrado como <b>{perfil}</b>!"
        }
    )
@router.get("/estoque")
async def tela_estoque(request: Request):
    return templates.TemplateResponse(
        "estoque.html",
        {"request": request}
    )
@router.post("/estoque_dados")
async def estoque_dados(db: Session = Depends(get_db)):

    dados = db.query(
        Formulario.nome_modelo.label("modelo"),
        Funcao.nome.label("funcao"),
        func.sum(Producao.quantidade).label("quantidade")
    ).join(
        Ficha, Ficha.id == Producao.ficha_id
    ).join(
        Formulario, Formulario.id == Ficha.formulario_id
    ).join(
        Funcao, Funcao.id == Producao.funcao_id
    ).group_by(
        Formulario.nome_modelo,
        Funcao.nome
    ).all()


    funcoes_corte = {
        "CORTADOR","AMONTOADOR","COLADOR","REFORCADOR","REFORCO"
    }

    funcoes_costura = {
        "BAIXA COSTURA","EMENDAR DORSO","FECHAR LUVA","LUVA COMPLETA",
        "PASSAR VIES","PREGAR OVO + ELASTICO","FECHAR LUVA + PREGAR PUNHO MALHA",
        "PREGAR OVO","PREGAR ELASTICO","PREGAR DORSO + FIVELA",
        "PREGAR FORCHETA","PREGAR DEDÃO","PREGAR DEDAO"
    }

    funcoes_acabamento = {
        "REFILAR","PASSAR","PASSAR LUVA",
        "REVISAR E EMPACOTAR","VIRADOR",
        "VIRAR-PASSAR-REVISAR E EMPACOTAR",
        "PASSAR-REVISAR E EMPACOTAR"
    }


    corte = {}
    costura = {}
    acabamento = {}

    for d in dados:

        modelo = d.modelo
        funcao = d.funcao.upper()
        qtd = int(d.quantidade)

        if funcao in funcoes_corte:
            corte[modelo] = corte.get(modelo,0) + qtd

        elif funcao in funcoes_costura:
            costura[modelo] = costura.get(modelo,0) + qtd

        elif funcao in funcoes_acabamento:
            acabamento[modelo] = acabamento.get(modelo,0) + qtd


    resultado = {}

    modelos = set(list(corte.keys()) + list(costura.keys()) + list(acabamento.keys()))

    for modelo in modelos:

        qtd_corte = corte.get(modelo,0)
        qtd_costura = costura.get(modelo,0)
        qtd_acab = acabamento.get(modelo,0)

        estoque_corte = max(qtd_corte - qtd_costura,0)
        estoque_costura = max(qtd_costura - qtd_acab,0)
        estoque_acab = qtd_acab

        resultado[modelo] = {
            "corte": estoque_corte,
            "costura": estoque_costura,
            "acabamento": estoque_acab
        }

    return resultado
# ======================================================
# VALORES POR MODELO
# ======================================================
@router.post("/modelos/add_valor")
#@admin_required
async def add_valor_modelo(
    modelo_id: int = Form(...),
    funcao_id: int = Form(...),
    valor: float = Form(...),
    db: Session = Depends(get_db)
):
    # verifica se já existe valor para esse modelo + função
    existente = (
        db.query(ValorModelo)
        .filter(
            ValorModelo.modelo_id == modelo_id,
            ValorModelo.funcao_id == funcao_id
        )
        .first()
    )

    if existente:
        existente.valor = valor
    else:
        novo = ValorModelo(
            modelo_id=modelo_id,
            funcao_id=funcao_id,
            valor=valor
        )
        db.add(novo)

    db.commit()
    return RedirectResponse("/modelos", status_code=303)

# ======================================================
# GERAR FICHAS (HTML)
# ======================================================

@router.get("/gerar_fichas", response_class=HTMLResponse)
@admin_required
async def gerar_fichas_page(
    request: Request,
    db: Session = Depends(get_db)
):
    modelos = db.query(Formulario).filter(
        Formulario.ativo == True
    ).order_by(Formulario.nome_modelo.asc()).all()

    return templates.TemplateResponse(
        "gerar_fichas.html",
        {"request": request, "modelos": modelos}
    )

# ======================================================
# GERAR FICHAS (PDF + QR)
# ======================================================
@router.get("/consultar_producao/pdf")
async def gerar_relatorio_pdf(
    operador: int = Query(...),
    data_inicial: str | None = Query(None),  # formato YYYY-MM-DD
    data_final: str | None = Query(None),
    db: Session = Depends(get_db),
):
    # =========================
    # BUSCAR NOME DO OPERADOR
    # =========================
    nome_operador = (
        db.query(UsuarioOperacional.nome)
        .filter(UsuarioOperacional.id == operador)
        .scalar()
    )

    if not nome_operador:
        raise HTTPException(status_code=404, detail="Operador não encontrado")

    # =========================
    # TRATAR DATAS (dia inteiro)
    # =========================
    dt_ini = None
    dt_fim = None

    if data_inicial:
        dt_ini = datetime.strptime(data_inicial, "%Y-%m-%d")

    if data_final:
        dt_fim = datetime.strptime(data_final, "%Y-%m-%d") + timedelta(days=1)

    # =========================
    # QUERY AGRUPADA
    # =========================
    query = (
        db.query(
            Formulario.nome_modelo.label("modelo"),
            Funcao.nome.label("funcao"),
            func.sum(Producao.quantidade).label("quantidade"),
            func.coalesce(ValorModelo.valor, 0).label("valor_unitario"),
        )
        .join(Ficha, Ficha.id == Producao.ficha_id)
        .join(Formulario, Formulario.id == Ficha.formulario_id)
        .join(Funcao, Funcao.id == Producao.funcao_id)
        .join(UsuarioOperacional, UsuarioOperacional.id == Producao.usuario_id)
        .outerjoin(
            ValorModelo,
            (ValorModelo.modelo_id == Formulario.id)
            & (ValorModelo.funcao_id == Producao.funcao_id),
        )
        .filter(Producao.usuario_id == operador)
    )

    if dt_ini:
        query = query.filter(Producao.criado_em >= dt_ini)

    if dt_fim:
        query = query.filter(Producao.criado_em < dt_fim)

    query = query.group_by(
        Formulario.nome_modelo,
        Funcao.nome,
        ValorModelo.valor,
    ).order_by(Formulario.nome_modelo, Funcao.nome)

    resultados = query.all()

    # =========================
    # GERAR PDF
    # =========================
    buffer = io.BytesIO()
    c = canvas.Canvas(buffer, pagesize=A4)

    y = 27 * cm
    total_geral = 0.0

    # Título
    c.setFont("Helvetica-Bold", 16)
    c.drawString(2 * cm, y, "Relatório de Produção")
    y -= 1 * cm

    # Operador
    c.setFont("Helvetica", 12)
    c.drawString(2 * cm, y, f"Operador: {nome_operador} (ID {operador})")
    y -= 0.7 * cm

    # Período
    if data_inicial or data_final:
        c.drawString(
            2 * cm,
            y,
            f"Período: {data_inicial or '---'} até {data_final or '---'}",
        )
        y -= 0.7 * cm

    y -= 0.3 * cm
    c.line(2 * cm, y, 19 * cm, y)
    y -= 0.8 * cm

    # Cabeçalho tabela
    c.setFont("Helvetica-Bold", 11)
    c.drawString(2 * cm, y, "Modelo")
    c.drawString(8 * cm, y, "Função")
    c.drawString(12 * cm, y, "Qtd")
    c.drawString(14 * cm, y, "Valor")
    c.drawString(17 * cm, y, "Total")

    y -= 0.6 * cm
    c.setFont("Helvetica", 11)

    # Linhas agrupadas
    for r in resultados:
        total = float(r.quantidade or 0) * float(r.valor_unitario or 0)
        total_geral += total

        c.drawString(2 * cm, y, r.modelo)
        c.drawString(8 * cm, y, r.funcao)
        c.drawRightString(13 * cm, y, str(r.quantidade or 0))
        c.drawRightString(16 * cm, y, f"R$ {r.valor_unitario:.2f}")
        c.drawRightString(19 * cm, y, f"R$ {total:.2f}")

        y -= 0.6 * cm

        if y < 2 * cm:
            c.showPage()
            y = 27 * cm
            c.setFont("Helvetica", 11)

    # Total Geral
    y -= 0.8 * cm
    c.setFont("Helvetica-Bold", 13)
    c.drawRightString(19 * cm, y, f"TOTAL GERAL: R$ {total_geral:.2f}")

    c.showPage()
    c.save()

    buffer.seek(0)

    return StreamingResponse(
        buffer,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f"attachment; filename=relatorio_{operador}.pdf"
        },
    )
