from fastapi import FastAPI, Depends, HTTPException, Query
from fastapi import Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from backend.database import SessionLocal, engine, Base
from backend.models import Producao, Ficha, Usuario, UsuarioOperacional, ValorModelo
from backend.schemas import ProducaoCreate, ProducaoResponse
from typing import List
from starlette.middleware.sessions import SessionMiddleware
import qrcode
import io
import base64
from datetime import datetime
from fastapi import File, UploadFile
import shutil, os


# Cria as tabelas se ainda não existirem
Base.metadata.create_all(bind=engine)

templates = Jinja2Templates(directory="backend/frontend/templates")
templates.env.globals['now'] = datetime.now
# Cria o app
app = FastAPI(title="Sistema de Produção Dadalto")

# Caminho absoluto para a pasta de uploads
UPLOAD_DIR = os.path.join("frontend", "static")

# Monta rota /static para servir imagens
app.mount("/static", StaticFiles(directory=UPLOAD_DIR), name="static")

# Adiciona o middleware de sessão
app.add_middleware(SessionMiddleware, secret_key="supersegredo123")

# Configuração de templates e arquivos estáticos
app.mount("/static", StaticFiles(directory="backend/frontend/static"), name="static")

# Dependência para obter sessão do banco
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@app.get("/")
def root():
    return {"mensagem": "🚀 API conectada ao banco 'producao' com sucesso!"}

# ✅ Rota para listar lançamentos com filtro e formatação de data
@app.get("/producoes", response_model=List[ProducaoResponse])
def listar_producoes(
    data_inicial: str | None = Query(None, description="Filtra por data inicial no formato DD-MM-YYYY"),
    data_final: str | None = Query(None, description="Filtra por data final no formato DD-MM-YYYY"),
    db: Session = Depends(get_db)
):
    query = db.query(Producao)

    # Filtro por intervalo de datas
    if data_inicial:
        try:
            inicio = datetime.strptime(data_inicial, "%d-%m-%Y")
            query = query.filter(Producao.criado_em >= inicio)
        except ValueError:
            raise HTTPException(status_code=400, detail="Data inicial inválida. Use o formato DD-MM-YYYY.")

    if data_final:
        try:
            fim = datetime.strptime(data_final, "%d-%m-%Y")
            query = query.filter(Producao.criado_em <= fim)
        except ValueError:
            raise HTTPException(status_code=400, detail="Data final inválida. Use o formato DD-MM-YYYY.")

    producoes = query.order_by(Producao.criado_em.desc()).all()

    # Retorno formatado
    return [
        {
            "id": p.id,
            "operador": p.operador,
            "produto": p.produto,
            "quantidade": p.quantidade,
            "valor": p.valor,
            "criado_em": p.criado_em.strftime("%d-%m-%Y %H:%M:%S")
        }
        for p in producoes
    ]
@app.get("/modelos", response_class=HTMLResponse)
async def modelos_page(request: Request, db: Session = Depends(get_db)):
    modelos = db.query(Formulario).all()
    valores = db.query(ValorModelo).all()
    return templates.TemplateResponse(
        "modelos.html",
        {"request": request, "modelos": modelos, "valores": valores}
    )

@app.post("/modelos/add")
async def add_modelo(nome_modelo: str = Form(...), db: Session = Depends(get_db)):
    novo = Formulario(nome_modelo=nome_modelo)
    db.add(novo)
    db.commit()
    return RedirectResponse("/modelos", status_code=303)

from fastapi import HTTPException
from sqlalchemy.exc import IntegrityError

@app.post("/modelos/add_valor")
async def add_valor(request: Request, db: Session = Depends(get_db)):
    form = await request.form()
    modelo_id = int(form.get("modelo_id"))
    funcao = form.get("funcao").strip()
    valor_unitario = float(form.get("valor_unitario").replace(",", "."))
    tamanho = form.get("tamanho") or None

    novo_valor = ValorModelo(
        modelo_id=modelo_id,
        funcao=funcao,
        valor_unitario=valor_unitario,
        tamanho=tamanho
    )

    db.add(novo_valor)
    try:
        db.commit()
    except Exception as e:
        db.rollback()
        print(e)
        raise HTTPException(status_code=400, detail="Erro ao salvar valor (já existe?)")

    return RedirectResponse(url="/modelos", status_code=303)
@app.post("/modelos/editar_inline")
async def editar_valor_inline(
    id: int = Form(...),
    modelo_id: int = Form(...),
    funcao: str = Form(...),
    valor_unitario: float = Form(...),
    tamanho: str = Form(None),
    db: Session = Depends(get_db)
):
    valor = db.query(ValorModelo).filter(ValorModelo.id == id).first()
    if not valor:
        raise HTTPException(status_code=404, detail="Valor não encontrado.")
    
    valor.modelo_id = modelo_id
    valor.funcao = funcao.strip()
    valor.valor_unitario = valor_unitario
    valor.tamanho = tamanho

    try:
        db.commit()
    except Exception as e:
        db.rollback()
        print(e)
        raise HTTPException(status_code=400, detail="Erro ao atualizar valor.")

    return RedirectResponse("/modelos", status_code=303)

# ✅ Rota para listar lançamentos
@app.get("/producoes", response_model=List[ProducaoResponse])
def listar_producoes(db: Session = Depends(get_db)):
    return db.query(Producao).all()
from sqlalchemy import func

from sqlalchemy import func
from datetime import datetime
from fastapi import Query

# ✅ Rota de resumo com filtros opcionais
@app.get("/resumo")
def resumo_por_operador(
    operador: str | None = Query(None, description="Filtra por nome do operador"),
    data_inicial: str | None = Query(None, description="Data inicial no formato YYYY-MM-DD"),
    data_final: str | None = Query(None, description="Data final no formato YYYY-MM-DD"),
    db: Session = Depends(get_db)
):
    
    # Inicia a query base
    query = db.query(
        Producao.operador,
        func.sum(Producao.quantidade).label("total_pecas"),
        func.sum(Producao.valor * Producao.quantidade).label("total_valor")
    )

    # Filtro por operador
    if operador:
        query = query.filter(Producao.operador.ilike(f"%{operador}%"))

    # Filtro por intervalo de datas
    if data_inicial:
     try:
        inicio = datetime.strptime(data_inicial, "%d-%m-%Y")
        query = query.filter(Producao.criado_em >= inicio)
     except ValueError:
        raise HTTPException(status_code=400, detail="Data inicial inválida. Use o formato DD-MM-YYYY.")
    
    if data_final:
     try:
        fim = datetime.strptime(data_final, "%d-%m-%Y")
        query = query.filter(Producao.criado_em <= fim)
     except ValueError:
        raise HTTPException(status_code=400, detail="Data final inválida. Use o formato DD-MM-YYYY.")
    
    # Agrupamento
    resultado = query.group_by(Producao.operador).all()

    # Retorno formatado
    return [
        {
            "operador": linha.operador,
            "total_pecas": linha.total_pecas,
            "total_valor": round(linha.total_valor, 2)
        }
        for linha in resultado
    ]

from backend.models import Ficha, StatusFicha
from backend.schemas import FichaCreate, FichaResponse

# ✅ Gerador de número sequencial (F0001, F0002, etc.)
def gerar_numero_ficha(db: Session):
    ultima = db.query(Ficha).order_by(Ficha.id.desc()).first()
    if not ultima:
        return "F0001"
    numero = int(ultima.numero_ficha[1:]) + 1
    return f"F{numero:04d}"

# ✅ Criar ficha nova
@app.post("/fichas", response_model=FichaResponse)
def criar_ficha(dados: FichaCreate, db: Session = Depends(get_db)):
    numero = gerar_numero_ficha(db)
    nova_ficha = Ficha(
        numero_ficha=numero,
        modelo=dados.modelo,
        funcao=dados.funcao,
        quantidade_total=dados.quantidade_total,
        setor_atual=dados.setor_atual,
    )
    db.add(nova_ficha)
    db.commit()
    db.refresh(nova_ficha)
    return nova_ficha

# ✅ Listar fichas
@app.get("/fichas", response_model=list[FichaResponse])
def listar_fichas(db: Session = Depends(get_db)):
    return db.query(Ficha).order_by(Ficha.id.desc()).all()


@app.post("/lancar", response_model=ProducaoResponse)
def lancar_producao(dados: ProducaoCreate, db: Session = Depends(get_db)):
    # 🔹 Verifica se a ficha existe
    ficha = db.query(Ficha).filter(Ficha.id == dados.ficha_id).first()
    if not ficha:
        raise HTTPException(status_code=404, detail="Ficha não encontrada")

    # 🔹 Cria o lançamento vinculado à ficha
    nova_ficha = Producao(**dados.dict())
    db.add(nova_ficha)
    db.commit()
    db.refresh(nova_ficha)
    return nova_ficha

# ===== LOGIN =====
@app.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    return templates.TemplateResponse("login.html", {"request": request, "erro": False})


@app.post("/login", response_class=HTMLResponse)
async def login_post(request: Request, usuario: str = Form(...), senha: str = Form(...)):
    db = SessionLocal()
    user = db.query(Usuario).filter_by(nome=usuario, senha=senha).first()
    db.close()

    # Se usuário não existe → erro
    if not user:
        return templates.TemplateResponse(
            "login.html",
            {"request": request, "erro": True}
        )

    # Se encontrou → cria sessão
    response = RedirectResponse(url="/dashboard", status_code=303)
    request.session["usuario"] = user.nome
    request.session["perfil"] = user.perfil
    return response


@app.get("/logout")
async def logout():
    return RedirectResponse(url="/login")

@app.get("/dashboard", response_class=HTMLResponse)
async def dashboard(request: Request):
    usuario = request.session.get("usuario")
    perfil = request.session.get("perfil")

    if not usuario:
        return RedirectResponse(url="/login")

    return templates.TemplateResponse("dashboard.html", {
        "request": request,
        "usuario": usuario,
        "perfil": perfil
    })

    # ==== Páginas do sistema (placeholders) ====

@app.get("/producao", response_class=HTMLResponse)
async def pagina_producao(request: Request):
    return templates.TemplateResponse("pagina.html", {"request": request, "titulo": "Consulta de Produção"})

@app.get("/fichas", response_class=HTMLResponse)
async def pagina_fichas(request: Request):
    return templates.TemplateResponse("pagina.html", {"request": request, "titulo": "Consulta de Fichas"})

@app.get("/estoque", response_class=HTMLResponse)
async def pagina_estoque(request: Request):
    return templates.TemplateResponse("pagina.html", {"request": request, "titulo": "Estoque de Produção"})

@app.get("/funcionarios", response_class=HTMLResponse)
async def pagina_funcionarios(request: Request):
    return templates.TemplateResponse("pagina.html", {"request": request, "titulo": "Controle de Funcionários"})

@app.get("/admin", response_class=HTMLResponse)
async def pagina_admin(request: Request):
    return templates.TemplateResponse("pagina.html", {"request": request, "titulo": "Administração do Sistema"})

# ===== Página de Lançamento (GET) =====

@app.get("/lancar", response_class=HTMLResponse)
async def lancar_page(request: Request, db: Session = Depends(get_db)):
    # Buscar todos os operadores e modelos ativos
    operadores = db.query(UsuarioOperacional).filter(UsuarioOperacional.ativo == 1).all()
    modelos = db.query(Formulario).filter(Formulario.ativo == True).all()
    
    return templates.TemplateResponse(
        "lancar.html",
        {"request": request, "operadores": operadores, "modelos": modelos}
    )


# ===== Receber envio do formulário (POST) =====
@app.post("/lancar", response_class=HTMLResponse)
async def lancar_post(request: Request):
    form = await request.form()
    operador = form.get("operador")
    modelo = form.get("modelo")
    funcao = form.get("funcao")
    quantidade = int(form.get("quantidade"))
    qtd_fichas = int(form.get("qtd_fichas"))
    numero_inicial = int(form.get("numero_inicial"))

    # Geração automática dos números das fichas
    fichas = [str(numero_inicial + i) for i in range(qtd_fichas)]

    # Monta o resumo pra exibição
    mensagem = (
        f"<b>Operador:</b> {operador}<br>"
        f"<b>Modelo:</b> {modelo}<br>"
        f"<b>Função:</b> {funcao}<br>"
        f"<b>Qtd por ficha:</b> {quantidade}<br>"
        f"<b>Fichas geradas:</b> {', '.join(fichas)}"
    )

    return templates.TemplateResponse("pagina.html", {
        "request": request,
        "titulo": "Lançamento Concluído ✅",
        "mensagem": mensagem
    })


    # Aqui futuramente faremos o INSERT no banco (por enquanto só exibe)
    return templates.TemplateResponse("pagina.html", {
        "request": request,
        "titulo": "Lançamento Concluído",
        "mensagem": f"Ficha lançada para {operador} - {modelo} ({quantidade} peças)"
    })

@app.get("/consultar_fichas", response_class=HTMLResponse)
async def consultar_fichas(request: Request):
    perfil = request.session.get("perfil", "")
    return templates.TemplateResponse("consultar_fichas.html", {"request": request, "perfil": perfil})

# Página de consulta de produção por funcionário
@app.get("/consultar_producao", response_class=HTMLResponse)
async def consultar_producao(request: Request):
    return templates.TemplateResponse("consultar_producao.html", {"request": request})

@app.get("/cadastro_formulario", response_class=HTMLResponse)
async def cadastro_formulario_page(request: Request, db: Session = Depends(get_db)):
    modelos = db.query(Formulario).order_by(Formulario.nome_modelo.asc()).all()
    return templates.TemplateResponse(
        "cadastro_formulario.html",
        {"request": request, "modelos": modelos}
    )

@app.post("/cadastro_formulario", response_class=HTMLResponse)
async def cadastro_formulario_post(request: Request,
                                   nome_modelo: str = Form(...),
                                   cor: str = Form(""),
                                   tamanhos: list[str] = Form([]),
                                   link: str = Form("")):
    db = SessionLocal()

    # Verifica se o modelo já existe
    existente = db.query(Formulario).filter(Formulario.nome_modelo == nome_modelo).first()
    if existente:
        existente.tamanhos = ",".join(tamanhos)
        existente.ativo = True
        db.commit()
        mensagem = f"🔄 Modelo <b>{nome_modelo}</b> atualizado com sucesso!"
    else:
        novo = Formulario(
            nome_modelo=nome_modelo,
            tamanhos=",".join(tamanhos),
            ativo=True
        )
        db.add(novo)
        db.commit()
        mensagem = f"✅ Novo modelo <b>{nome_modelo}</b> cadastrado com sucesso!"

    modelos = db.query(Formulario).order_by(Formulario.nome_modelo.asc()).all()
    db.close()

    return templates.TemplateResponse("cadastro_formulario.html", {
        "request": request,
        "modelos": modelos,
        "mensagem": mensagem
    })

# ===== Página de Administração =====
@app.get("/administracao", response_class=HTMLResponse)
async def administracao_page(request: Request):
    return templates.TemplateResponse("administracao.html", {"request": request})

# ===== Cadastrar novos usuários operacionais =====

@app.get("/cadastrar_usuario", response_class=HTMLResponse)
async def cadastrar_usuario_page(request: Request):
    return templates.TemplateResponse("cadastrar_usuario.html", {"request": request})


@app.post("/cadastrar_usuario", response_class=HTMLResponse)
async def cadastrar_usuario(request: Request,
                            nome: str = Form(...),
                            senha: str = Form(...),
                            perfil: str = Form(...)):
    db = SessionLocal()

    # Verifica se o usuário já existe
    usuario_existente = db.query(Usuario).filter(Usuario.nome == nome).first()
    if usuario_existente:
        db.close()
        mensagem = f"⚠️ O usuário <b>{nome}</b> já está cadastrado!"
        return templates.TemplateResponse("cadastrar_usuario.html", {
            "request": request,
            "mensagem": mensagem
        })

    # Cria novo usuário (na tabela correta)
    novo_usuario = Usuario(nome=nome, senha=senha, perfil=perfil)
    db.add(novo_usuario)
    db.commit()
    db.close()

    mensagem = f"✅ Usuário <b>{nome}</b> cadastrado com sucesso como <b>{perfil}</b>!"
    return templates.TemplateResponse("cadastrar_usuario.html", {
        "request": request,
        "mensagem": mensagem
    })

# ==== Login de Operador ====
@app.get("/login_operador", response_class=HTMLResponse)
async def login_operador_page(request: Request):
    return templates.TemplateResponse("login_operador.html", {"request": request})

@app.post("/login_operador", response_class=HTMLResponse)
async def login_operador_post(request: Request):
    form = await request.form()
    nome = form.get("nome")
    senha = form.get("senha")

    db = SessionLocal()
    usuario = db.query(UsuarioOperacional).filter_by(nome=nome, senha=senha).first()

    if not usuario:
        return templates.TemplateResponse(
            "login_operador.html",
            {"request": request, "erro": "Usuário ou senha incorretos"}
        )

   
    @app.get("/formulario_operador", response_class=HTMLResponse)
    async def formulario_operador_page(request: Request, token: str, db: Session = Depends(get_db)):
     ficha = db.query(Ficha).filter(Ficha.token_qr == token).first()
     operador = request.session.get("usuario", "")  # se estiver logado
     return templates.TemplateResponse("formulario_operador.html", {
        "request": request,
        "ficha": ficha,
        "operador": operador
    })

UPLOAD_DIR = "frontend/static/uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)

@app.post("/formularios/novo")
async def criar_formulario(
    request: Request,
    nome_modelo: str = Form(...),
    url_imagem: UploadFile = File(None),
    db: Session = Depends(get_db)
):
    nome_modelo = nome_modelo.strip()
    UPLOAD_DIR = "frontend/static/uploads"
    os.makedirs(UPLOAD_DIR, exist_ok=True)
    
    image_path = None

    if url_imagem:
        filename = f"{nome_modelo.replace(' ', '')}{url_imagem.filename}"
        save_path = os.path.join(UPLOAD_DIR, filename)
        with open(save_path, "wb") as buffer:
            shutil.copyfileobj(url_imagem.file, buffer)
        image_path = f"/static/uploads/{filename}"

    # Cria novo formulário
    novo = Formulario(nome_modelo=nome_modelo, url_imagem=image_path, ativo=True)
    db.add(novo)
    db.commit()
    db.refresh(novo)

    # Redireciona de volta à tela principal
    return RedirectResponse(url="/cadastro_formulario", status_code=303)

@app.get("/funcionarios", response_class=HTMLResponse)
async def funcionarios_page(request: Request):
    return templates.TemplateResponse("funcionarios.html", {"request": request})

# ==== CONSULTA DE PRODUÇÃO ====
from sqlalchemy import func
from fastapi.responses import JSONResponse

@app.get("/consultar_producao", response_class=HTMLResponse)
async def consultar_producao_page(request: Request):
    db = SessionLocal()
    operadores = db.query(Producao.operador).distinct().order_by(Producao.operador.asc()).all()
    modelos = db.query(Producao.modelo).distinct().order_by(Producao.modelo.asc()).all()
    db.close()

    return templates.TemplateResponse("consultar_producao.html", {
        "request": request,
        "operadores": [o[0] for o in operadores],
        "modelos": [m[0] for m in modelos]
    })

@app.post("/consultar_producao_dados")
async def consultar_producao_dados(
    operador: str = Form(...),
    data_inicial: str = Form(None),
    data_final: str = Form(None),
    db: Session = Depends(get_db)
):
    query = db.query(Producao).filter(Producao.operador.ilike(f"%{operador}%"))

    # Filtros de data, se existirem
    if data_inicial:
        query = query.filter(Producao.criado_em >= data_inicial)
    if data_final:
        query = query.filter(Producao.criado_em <= data_final)

    resultados = query.order_by(Producao.criado_em.desc()).all()

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
    # ==============================
# IMPORTS (deixe junto dos demais)
# ==============================
import secrets
from io import BytesIO
from fastapi.responses import StreamingResponse
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from reportlab.lib.units import cm

# vamos usar o catálogo de modelos em "formularios"
from backend.models import Formulario

# ------------------------------
# util: próxima ficha (começa em 8000)
# ------------------------------
def proxima_ficha_numero(db: Session) -> int:
    """
    Busca o maior numero_ficha (inteiro) na tabela e retorna próximo.
    Se não houver, começa em 8000.
    """
    ultimo = db.query(Ficha).order_by(Ficha.id.desc()).first()
    if not ultimo or not str(ultimo.numero_ficha).isdigit():
        return 8000
    n = int(ultimo.numero_ficha)
    return max(8000, n + 1)

# ------------------------------
# util: quantidade padrão por modelo
# ------------------------------
def quantidade_padrao_por_modelo(nome_modelo: str) -> int:
    # regra solicitada: luvas = 50; acessórios = 20
    if "LUVA" in (nome_modelo or "").upper():
        return 50
    return 20
# ==============================
# GERAR FICHAS (com PDF e QR)
# ==============================
from fastapi.responses import FileResponse
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import cm
from reportlab.pdfgen import canvas
from reportlab.lib.utils import ImageReader
import qrcode
import io
import uuid

@app.post("/gerar_fichas")
async def gerar_fichas(request: Request, modelo: str = Form(...), qtd_fichas: int = Form(...)):
    db = SessionLocal()

    try:
        # pega a última ficha existente
        ultima_ficha = db.query(Ficha).order_by(Ficha.id.desc()).first()
        proximo_numero = 8000 if not ultima_ficha else int(ultima_ficha.numero_ficha) + 1

        # define quantidade padrão por tipo
        quantidade = 50 if "LUVA" in modelo.upper() else 20

        fichas = []

        # gera e salva no banco
        for i in range(qtd_fichas):
            token_qr = str(uuid.uuid4())  # ✅ token único
            nova = Ficha(
                numero_ficha=str(proximo_numero + i),
                modelo=modelo,
                funcao="GERAL",
                quantidade_total=quantidade,
                setor_atual="CORTE",
                token_qr=token_qr  # ✅ usa o token correto
            )
            db.add(nova)
            fichas.append(nova)

        db.commit()

        # === Geração do PDF ===
        pdf_path = "fichas_geradas.pdf"
        c = canvas.Canvas(pdf_path, pagesize=A4)

        for ficha in fichas:
            qr_url = f"http://127.0.0.1:8000/responder_ficha?token={ficha.token_qr}"  # ✅ token certo
            qr_img = qrcode.make(qr_url)
            buffer = io.BytesIO()
            qr_img.save(buffer, format="PNG")
            buffer.seek(0)
            qr_image = ImageReader(buffer)

            # Cabeçalho
            c.setFont("Helvetica-Bold", 24)
            c.drawCentredString(10.5 * cm, 27 * cm, f"FICHA Nº {ficha.numero_ficha}")
            c.setFont("Helvetica", 18)
            c.drawCentredString(10.5 * cm, 25 * cm, f"MODELO: {ficha.modelo}")
            c.setFont("Helvetica", 16)
            c.drawCentredString(10.5 * cm, 23.5 * cm, f"QUANTIDADE: {ficha.quantidade_total} PEÇAS")

            # QR centralizado
            c.drawImage(qr_image, 6.5 * cm, 13 * cm, width=8 * cm, height=8 * cm)
            c.showPage()

        c.save()

        return FileResponse(pdf_path, filename="fichas_geradas.pdf", media_type="application/pdf")

    except Exception as e:
        print("Erro ao gerar fichas:", e)
        raise HTTPException(status_code=500, detail=str(e))

    finally:
        db.close()

@app.get("/gerar_fichas", response_class=HTMLResponse)
async def gerar_fichas_page(request: Request):
    db = SessionLocal()
    modelos = db.query(Formulario).filter(Formulario.ativo == True).all()
    db.close()
    return templates.TemplateResponse("gerar_fichas.html", {"request": request, "modelos": modelos})

# ==========================================================
# FORMULÁRIO DO QR (responder ficha)
# ==========================================================
FUNCOES_OPCOES = [
    "CORTADOR","AMONTOADOR","COLADOR","REFORCADOR","REFILAR","PASSAR","PASSAR LUVA",
    "REVISAR E EMPACOTAR","VIRADOR","BAIXA COSTURA","EMENDAR DORSO","FECHAR LUVA",
    "LUVA COMPLETA","PASSAR VIES","PREGAR OVO + ELASTICO",
    "FECHAR LUVA + PREGAR PUNHO MALHA","PREGAR OVO","PREGAR ELASTICO",
    "PREGAR DORSO + FIVELA","PREGAR FORCHETA","PREGAR DEDÃO","PREGAR DEDAO"
]

@app.get("/responder_ficha", response_class=HTMLResponse)
async def responder_ficha_page(request: Request, token: str, db: Session = Depends(get_db)):
    ficha = db.query(Ficha).filter(Ficha.token_qr == token).first()
    operador = request.session.get("usuario", "")

    if not ficha:
        return HTMLResponse("<h3>Ficha não encontrada ou QR inválido.</h3>", status_code=404)
    
    form_modelo = db.query(Formulario).filter(Formulario.nome_modelo == ficha.modelo).first()
    url_imagem = form_modelo.url_imagem if form_modelo and form_modelo.url_imagem else None

    return templates.TemplateResponse("responder_ficha_operador.html", {
        "request": request,
        "ficha": ficha,          # ✅ envia o objeto ficha pro template
        "token": token,
        "operador": operador,
        "numero_ficha": ficha.numero_ficha,
        "modelo": ficha.modelo,
        "quantidade": ficha.quantidade_total,
        "funcoes": FUNCOES_OPCOES,
        "url_imagem": url_imagem,
    })

@app.post("/responder_ficha", response_class=HTMLResponse)
async def responder_ficha_submit(
    request: Request,
    token: str = Form(...),
    operador: str = Form(...),
    funcao: str = Form(...),
    quantidade: int = Form(...),
):
    db = SessionLocal()
    try:
        ficha = db.query(Ficha).filter(Ficha.token_qr == token).first()
        if not ficha:
            db.close()
            return templates.TemplateResponse(
                "pagina.html",
                {
                    "request": request,
                    "titulo": "Erro",
                    "mensagem": "Ficha não encontrada."
                },
            )

        # cria o registro de produção
        nova_producao = Producao(
            ficha_id=ficha.id,
            operador=operador.strip(),
            modelo=ficha.modelo,
            servico=funcao.strip(),
            tamanho=None,
            quantidade=quantidade,
            valor=0.0,
        )

        db.add(nova_producao)
        db.commit()

        # guarda infos antes de fechar
        numero_ficha = ficha.numero_ficha
        modelo = ficha.modelo
        db.close()

        # renderiza página de sucesso
        return templates.TemplateResponse(
            "pagina.html",
            {
                "request": request,
                "titulo": "Produção lançada ✅",
                "mensagem": f"Ficha {numero_ficha} lançada para {operador} ({funcao}) – {quantidade} peças do modelo {modelo}.",
            },
        )

    except Exception as e:
        db.rollback()
        print("Erro ao responder ficha:", e)
        return HTMLResponse(f"<h3>Erro: {e}</h3>", status_code=500)

    finally:
        db.close()