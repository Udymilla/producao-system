from fastapi import APIRouter, Request, Form, Depends, File, UploadFile
from fastapi.responses import HTMLResponse, RedirectResponse, FileResponse
from sqlalchemy.orm import Session
import os, shutil, uuid, io
import qrcode
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import cm
from reportlab.lib.utils import ImageReader
from backend.database import SessionLocal, get_db
from backend.models import Usuario, Formulario, ValorModelo, Ficha
from backend.security import admin_required
from backend.utils import templates

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

# ======================================================
# VALORES POR MODELO
# ======================================================

@router.post("/modelos/add_valor")
@admin_required
async def add_valor(request: Request, db: Session = Depends(get_db)):
    form = await request.form()

    novo = ValorModelo(
        modelo_id=int(form.get("modelo_id")),
        funcao=form.get("funcao"),
        valor_unitario=float(form.get("valor_unitario").replace(",", ".")),
        tamanho=form.get("tamanho")
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

@router.post("/gerar_fichas")
@admin_required
async def gerar_fichas(
    request: Request,
    formulario_id: int = Form(...),
    qtd_fichas: int = Form(...),
    db: Session = Depends(get_db)
):
    formulario = db.query(Formulario).get(formulario_id)
    if not formulario:
        raise Exception("Modelo não encontrado")

    ultima = db.query(Ficha).order_by(Ficha.id.desc()).first()
    proximo_numero = 8000 if not ultima else int(ultima.numero_ficha) + 1

    quantidade = 50 if "LUVA" in formulario.nome_modelo.upper() else 20
    fichas = []

    # ======================
    # 🗃️ CRIA FICHAS NO BD
    # ======================
    for i in range(qtd_fichas):
        ficha = Ficha(
            numero_ficha=str(proximo_numero + i),
            quantidade_total=quantidade,
            formulario_id=formulario.id,
            token_qr=str(uuid.uuid4())
        )
        db.add(ficha)
        fichas.append(ficha)

    db.commit()

    # ======================
    # 📄 GERA PDF + QR
    # ======================
    pdf_path = "fichas_geradas.pdf"
    c = canvas.Canvas(pdf_path, pagesize=A4)

    for ficha in fichas:
        qr_url = f"http://127.0.0.1:8000/responder_ficha?token={ficha.token_qr}"
        qr_img = qrcode.make(qr_url)

        buffer = io.BytesIO()
        qr_img.save(buffer, format="PNG")
        buffer.seek(0)
        qr_image = ImageReader(buffer)

        c.setFont("Helvetica-Bold", 24)
        c.drawCentredString(10.5 * cm, 27 * cm, f"FICHA Nº {ficha.numero_ficha}")

        c.setFont("Helvetica", 18)
        c.drawCentredString(
            10.5 * cm,
            25 * cm,
            f"MODELO: {ficha.formulario.nome_modelo}"
        )

        c.setFont("Helvetica", 16)
        c.drawCentredString(
            10.5 * cm,
            23.5 * cm,
            f"QUANTIDADE: {ficha.quantidade_total} PEÇAS"
        )

        c.drawImage(qr_image, 6.5 * cm, 13 * cm, width=8 * cm, height=8 * cm)

        c.showPage()

    c.save()

    return FileResponse(
        pdf_path,
        filename="fichas_geradas.pdf",
        media_type="application/pdf"
    )
