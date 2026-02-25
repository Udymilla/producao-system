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

# ======================================================
# FORMULÁRIOS / MODELOS
# ======================================================
@router.get("/modelos", response_class=HTMLResponse)
@admin_required
async def modelos_page(
    request: Request,
    db: Session = Depends(get_db)
):
    modelos = (
        db.query(Formulario)
        .filter(Formulario.ativo == True)
        .order_by(Formulario.nome_modelo)
        .all()
    )

    funcoes = (
        db.query(Funcao)
        .order_by(Funcao.nome)
        .all()
    )

    valores = (
        db.query(ValorModelo)
        .join(Formulario)
        .join(Funcao)
        .order_by(Formulario.nome_modelo, Funcao.nome)
        .all()
    )

    return templates.TemplateResponse(
        "modelos.html",
        {
            "request": request,
            "modelos": modelos,
            "funcoes": funcoes,
            "valores": valores
        }
    )

@router.get("/cadastro_formulario", response_class=HTMLResponse)
@admin_required
async def cadastro_formulario_page(
    request: Request,
    db: Session = Depends(get_db)
):
    modelos = db.query(Formulario).order_by(Formulario.nome_modelo.asc()).all()

    return templates.TemplateResponse(
        "cadastro_formulario.html",
        {"request": request, "modelos": modelos}
    )

@router.post("/cadastro_formulario", response_class=HTMLResponse)
@admin_required
async def cadastro_formulario_post(
    request: Request,
    nome_modelo: str = Form(...),
    cor_vies: str = Form(""),
    ca: str = Form(""),
    tamanhos: list[str] = Form([]),
    db: Session = Depends(get_db)
):
    nome_modelo = nome_modelo.strip()

    existente = (
        db.query(Formulario)
        .filter(Formulario.nome_modelo == nome_modelo)
        .first()
    )

    if existente:
        existente.tamanhos = ",".join(tamanhos)
        existente.cor_vies = cor_vies
        existente.ca = ca
        existente.ativo = True
        db.commit()
        mensagem = f"🔄 Modelo <b>{nome_modelo}</b> atualizado!"
    else:
        novo = Formulario(
            nome_modelo=nome_modelo,
            tamanhos=",".join(tamanhos),
            cor_vies=cor_vies,
            ca=ca,
            ativo=True
        )
        db.add(novo)
        db.commit()
        mensagem = f"✅ Novo modelo <b>{nome_modelo}</b> cadastrado!"

    modelos = db.query(Formulario).order_by(Formulario.nome_modelo).all()

    return templates.TemplateResponse(
        "cadastro_formulario.html",
        {
            "request": request,
            "modelos": modelos,
            "mensagem": mensagem
        }
    )
@router.get("/consultar_producao/pdf")
async def gerar_relatorio_pdf(
    operador: str,
    data_inicial: str = None,
    data_final: str = None,
    db: Session = Depends(get_db)
):
    # ==========================
    # QUERY (a mesma da consulta)
    # ==========================
    query = (
        db.query(
            Formulario.nome_modelo.label("modelo"),
            Funcao.nome.label("funcao"),
            func.sum(Producao.quantidade).label("quantidade"),
            ValorModelo.valor.label("valor_unitario")
        )
        .join(Ficha, Ficha.id == Producao.ficha_id)
        .join(Formulario, Formulario.id == Ficha.formulario_id)
        .join(Funcao, Funcao.id == Producao.funcao_id)
        .join(UsuarioOperacional, UsuarioOperacional.id == Producao.usuario_id)
        .join(
            ValorModelo,
            (ValorModelo.modelo_id == Formulario.id) &
            (ValorModelo.funcao_id == Funcao.id)
        )
        .group_by(Formulario.nome_modelo, Funcao.nome, ValorModelo.valor)
        .order_by(Formulario.nome_modelo)
    )

    if operador:
        query = query.filter(Producao.usuario_id == int(operador))

    if data_inicial:
        query = query.filter(
            Producao.criado_em >= datetime.strptime(data_inicial, "%Y-%m-%d")
        )

    if data_final:
        query = query.filter(
            Producao.criado_em <= datetime.strptime(data_final, "%Y-%m-%d")
        )
        

    resultados = query.all()

    # ==========================
    # GERA PDF
    # ==========================
    buffer = io.BytesIO()
    c = canvas.Canvas(buffer, pagesize=A4)

    y = 27 * cm
    total_geral = 0

    c.setFont("Helvetica-Bold", 16)
    c.drawString(2 * cm, y, "Relatório de Produção")
    y -= 1 * cm

    c.setFont("Helvetica", 12)
    c.drawString(2 * cm, y, f"Operador: {operador}")
    y -= 0.8 * cm

    if data_inicial or data_final:
        c.drawString(
            2 * cm,
            y,
            f"Período: {data_inicial or '---'} até {data_final or '---'}"
        )
        y -= 1 * cm

    c.line(2 * cm, y, 19 * cm, y)
    y -= 0.8 * cm

    c.setFont("Helvetica-Bold", 11)
    c.drawString(2 * cm, y, "Modelo")
    c.drawString(7 * cm, y, "Função")
    c.drawString(11 * cm, y, "Qtd")
    c.drawString(13 * cm, y, "Valor")
    c.drawString(16 * cm, y, "Total")

    y -= 0.6 * cm
    c.setFont("Helvetica", 11)

    for r in resultados:
        total = r.quantidade * r.valor_unitario
        total_geral += total

        c.drawString(2 * cm, y, r.modelo)
        c.drawString(7 * cm, y, r.funcao)
        c.drawRightString(12.5 * cm, y, str(r.quantidade))
        c.drawRightString(15 * cm, y, f"R$ {r.valor_unitario:.2f}")
        c.drawRightString(19 * cm, y, f"R$ {total:.2f}")

        y -= 0.6 * cm

        if y < 2 * cm:
            c.showPage()
            y = 27 * cm

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
    }
)
   

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
    operador: int = Query(..., description="ID do operador"),
    data_inicial: str | None = Query(None, description="YYYY-MM-DD"),
    data_final: str | None = Query(None, description="YYYY-MM-DD"),
    db: Session = Depends(get_db),
):
    # --------------------------
    # 1) Nome do operador
    # --------------------------
    nome_operador = (
        db.query(UsuarioOperacional.nome)
        .filter(UsuarioOperacional.id == operador)
        .scalar()
    )
    if not nome_operador:
        raise HTTPException(status_code=404, detail="Operador não encontrado")

    # --------------------------
    # 2) Datas (igual tela: incluir o dia inteiro)
    # --------------------------
    dt_ini = None
    dt_fim_exclusivo = None

    if data_inicial:
        dt_ini = datetime.strptime(data_inicial, "%Y-%m-%d")

    if data_final:
        dt_fim_exclusivo = datetime.strptime(data_final, "%Y-%m-%d") + timedelta(days=1)

    # --------------------------
    # 3) Query NÃO AGRUPADA (lançamento por lançamento)
    # --------------------------
    valor_unitario_expr = func.coalesce(ValorModelo.valor, literal(0))

    query = (
        db.query(
            Ficha.numero_ficha.label("numero_ficha"),
            Formulario.nome_modelo.label("modelo"),
            Funcao.nome.label("funcao"),
            Producao.quantidade.label("quantidade"),
            Producao.criado_em.label("criado_em"),
            valor_unitario_expr.label("valor_unitario"),
        )
        .join(Ficha, Ficha.id == Producao.ficha_id)
        .join(Formulario, Formulario.id == Ficha.formulario_id)
        .join(Funcao, Funcao.id == Producao.funcao_id)
        .join(UsuarioOperacional, UsuarioOperacional.id == Producao.usuario_id)
        # valor pode não existir -> OUTERJOIN pra não sumir com o lançamento
        .outerjoin(
            ValorModelo,
            (ValorModelo.modelo_id == Formulario.id) &
            (ValorModelo.funcao_id == Producao.funcao_id)
        )
        .filter(Producao.usuario_id == operador)
        .order_by(Producao.criado_em.asc())
    )

    if dt_ini:
        query = query.filter(Producao.criado_em >= dt_ini)
    if dt_fim_exclusivo:
        query = query.filter(Producao.criado_em < dt_fim_exclusivo)

    resultados = query.all()

    # --------------------------
    # 4) PDF
    # --------------------------
    buffer = io.BytesIO()
    c = canvas.Canvas(buffer, pagesize=A4)

    y = 27 * cm
    total_geral = 0.0

    c.setFont("Helvetica-Bold", 16)
    c.drawString(2 * cm, y, "Relatório de Produção")
    y -= 1.0 * cm

    c.setFont("Helvetica", 12)
    c.drawString(2 * cm, y, f"Operador: {nome_operador} (ID {operador})")
    y -= 0.7 * cm

    if data_inicial or data_final:
        c.drawString(2 * cm, y, f"Período: {data_inicial or '---'} até {data_final or '---'}")
        y -= 0.7 * cm

    y -= 0.2 * cm
    c.line(2 * cm, y, 19 * cm, y)
    y -= 0.8 * cm

    # Cabeçalho
    c.setFont("Helvetica-Bold", 10)
    c.drawString(2.0 * cm, y, "Ficha")
    c.drawString(4.0 * cm, y, "Modelo")
    c.drawString(10.5 * cm, y, "Função")
    c.drawString(14.2 * cm, y, "Data/Hora")
    c.drawRightString(17.2 * cm, y, "Qtd")
    c.drawRightString(19.0 * cm, y, "Total")
    y -= 0.6 * cm

    c.setFont("Helvetica", 10)

    for r in resultados:
        total = float(r.quantidade or 0) * float(r.valor_unitario or 0)
        total_geral += total

        data_fmt = r.criado_em.strftime("%d/%m/%Y %H:%M") if r.criado_em else ""

        c.drawString(2.0 * cm, y, str(r.numero_ficha))
        c.drawString(4.0 * cm, y, (r.modelo or "")[:32])
        c.drawString(10.5 * cm, y, (r.funcao or "")[:20])
        c.drawString(14.2 * cm, y, data_fmt)
        c.drawRightString(17.2 * cm, y, str(r.quantidade or 0))
        c.drawRightString(19.0 * cm, y, f"R$ {total:.2f}")

        y -= 0.55 * cm
        if y < 2.0 * cm:
            c.showPage()
            y = 27 * cm
            c.setFont("Helvetica", 10)

    y -= 0.8 * cm
    c.setFont("Helvetica-Bold", 12)
    c.drawRightString(19.0 * cm, y, f"TOTAL GERAL: R$ {total_geral:.2f}")

    c.showPage()
    c.save()
    buffer.seek(0)

    return StreamingResponse(
        buffer,
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename=relatorio_{operador}.pdf"},
    )