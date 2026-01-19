from fastapi import APIRouter, Request, Form, Depends, File, UploadFile
from fastapi.responses import HTMLResponse, RedirectResponse, FileResponse
from backend.utils import templates
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

# ======================================================
# CONFIG
# ======================================================

router = APIRouter()

# ✅ caminho correto no seu projeto (você usa templates em backend/frontend/templates)
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
async def cadastrar_usuario(
    request: Request,
    nome: str = Form(...),
    senha: str = Form(...),
    perfil: str = Form(...)
):
    db = SessionLocal()

    existente = db.query(Usuario).filter(Usuario.nome == nome).first()
    if existente:
        db.close()
        mensagem = f"⚠️ O usuário <b>{nome}</b> já existe!"
        return templates.TemplateResponse(
            "cadastrar_usuario.html",
            {"request": request, "mensagem": mensagem}
        )

    novo = Usuario(nome=nome, senha=senha, perfil=perfil)
    db.add(novo)
    db.commit()
    db.close()

    mensagem = f"✅ Usuário <b>{nome}</b> cadastrado como <b>{perfil}</b>!"
    return templates.TemplateResponse(
        "cadastrar_usuario.html",
        {"request": request, "mensagem": mensagem}
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
    modelos = (
        db.query(Formulario)
        .order_by(Formulario.nome_modelo.asc())
        .all()
    )

    return templates.TemplateResponse(
        "cadastro_formulario.html",
        {"request": request, "modelos": modelos}
    )


@router.post("/cadastro_formulario", response_class=HTMLResponse)
@admin_required
async def cadastro_formulario_post(
    request: Request,
    nome_modelo: str = Form(...),
    cor: str = Form(""),
    tamanhos: list[str] = Form([]),
    link: str = Form(""),
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
        existente.ativo = True
        db.commit()
        mensagem = f"🔄 Modelo <b>{nome_modelo}</b> atualizado!"
    else:
        novo = Formulario(
            nome_modelo=nome_modelo,
            tamanhos=",".join(tamanhos),
            ativo=True
        )
        db.add(novo)
        db.commit()
        mensagem = f"✅ Novo modelo <b>{nome_modelo}</b> cadastrado!"

    modelos = (
        db.query(Formulario)
        .order_by(Formulario.nome_modelo.asc())
        .all()
    )

    return templates.TemplateResponse(
        "cadastro_formulario.html",
        {
            "request": request,
            "modelos": modelos,
            "mensagem": mensagem
        }
    )


@router.post("/formularios/novo")
@admin_required
async def criar_formulario(
    request: Request,
    nome_modelo: str = Form(...),
    url_imagem: UploadFile = File(None),
    db: Session = Depends(get_db)
):
    nome_modelo = nome_modelo.strip()
    image_path = None

    if url_imagem:
        filename = f"{nome_modelo.replace(' ', '')}_{url_imagem.filename}"
        save_path = os.path.join(UPLOAD_DIR, filename)

        with open(save_path, "wb") as buffer:
            shutil.copyfileobj(url_imagem.file, buffer)

        # ✅ a URL pública continua sendo /static/uploads/...
        image_path = f"/static/uploads/{filename}"

    novo = Formulario(
        nome_modelo=nome_modelo,
        url_imagem=image_path,
        ativo=True
    )
    db.add(novo)
    db.commit()

    return RedirectResponse(
        url="/cadastro_formulario",
        status_code=303
    )

# ======================================================
# VALORES POR MODELO
# ======================================================

@router.post("/modelos/add_valor")
@admin_required
async def add_valor(request: Request, db: Session = Depends(get_db)):
    form = await request.form()

    modelo_id = int(form.get("modelo_id"))
    funcao = (form.get("funcao") or "").strip()
    valor_unitario = float((form.get("valor_unitario") or "0").replace(",", "."))
    tamanho = form.get("tamanho") or None

    novo = ValorModelo(
        modelo_id=modelo_id,
        funcao=funcao,
        valor_unitario=valor_unitario,
        tamanho=tamanho
    )

    db.add(novo)
    db.commit()

    return RedirectResponse(
        url="/modelos",
        status_code=303
    )

# ======================================================
# GERAR FICHAS (HTML)
# ======================================================

@router.get("/gerar_fichas", response_class=HTMLResponse)
@admin_required
async def gerar_fichas_page(
    request: Request,
    db: Session = Depends(get_db)
):
    # ✅ AQUI É A CORREÇÃO PRINCIPAL:
    # carrega os modelos reais (Formulario) para preencher o select
    modelos = (
        db.query(Formulario)
        .filter(Formulario.ativo == True)
        .order_by(Formulario.nome_modelo.asc())
        .all()
    )

    return templates.TemplateResponse(
        "gerar_fichas.html",
        {
            "request": request,
            "modelos": modelos
        }
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
    # 🔎 Busca modelo oficial
    formulario = (
        db.query(Formulario)
        .filter(Formulario.id == formulario_id, Formulario.ativo == True)
        .first()
    )

    if not formulario:
        return templates.TemplateResponse(
            "gerar_fichas.html",
            {
                "request": request,
                "modelos": db.query(Formulario).filter(Formulario.ativo == True).all(),
                "mensagem": "⚠️ Modelo não encontrado."
            }
        )

    # 🔢 Sequência de ficha
    ultima = db.query(Ficha).order_by(Ficha.id.desc()).first()
    proximo_numero = 8000 if not ultima else int(ultima.numero_ficha) + 1

    # 📦 Regra de quantidade
    quantidade = 50 if "LUVA" in formulario.nome_modelo.upper() else 20

    fichas = []

    for i in range(qtd_fichas):
        token_qr = str(uuid.uuid4())

        ficha = Ficha(
            numero_ficha=str(proximo_numero + i),
            modelo_id=formulario.id,   # ✅ FK correta
            funcao="GERAL",
            quantidade_total=quantidade,
            setor_atual="CORTE",
            token_qr=token_qr
        )

        db.add(ficha)
        fichas.append(ficha)

    db.commit()

    # 🔄 garante acesso ao relacionamento
    for ficha in fichas:
        db.refresh(ficha)

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
            f"MODELO: {ficha.modelo_ref.nome_modelo}"  # ✅ relacionamento correto
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
