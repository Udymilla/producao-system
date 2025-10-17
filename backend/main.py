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

# Cria as tabelas se ainda não existirem
Base.metadata.create_all(bind=engine)

# Cria o app
app = FastAPI(title="Sistema de Produção Dadalto")

# Adiciona o middleware de sessão
app.add_middleware(SessionMiddleware, secret_key="supersegredo123")

# Configuração de templates e arquivos estáticos
app.mount("/static", StaticFiles(directory="backend/frontend/static"), name="static")
templates = Jinja2Templates(directory="backend/frontend/templates")

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

# ===== Cadastrar ou atualizar valor de modelo =====
@app.get("/valores_modelos", response_class=HTMLResponse)
async def listar_valores_modelos(request: Request):
    db = SessionLocal()
    valores = db.query(ValorModelo).order_by(ValorModelo.modelo.asc()).all()

    # 🔹 busca todos os modelos das tabelas fichas e produção
    modelos_fichas = db.query(Ficha.modelo).distinct().all()   # ✅ corrigido
    modelos_producao = db.query(Producao.modelo).distinct().all()

    # 🔹 junta e remove duplicados
    modelos = sorted(set([m[0] for m in modelos_fichas + modelos_producao if m[0]]))

    db.close()

    return templates.TemplateResponse("valores_modelos.html", {
        "request": request,
        "valores": valores,
        "modelos": modelos
    })

@app.post("/valores_modelos", response_class=HTMLResponse)
async def cadastrar_valor_modelo(request: Request, modelo: str = Form(...), valor: float = Form(...)):
    db = SessionLocal()
    existente = db.query(ValorModelo).filter(ValorModelo.modelo == modelo).first()

    if existente:
        existente.valor_unitario = valor  # atualiza valor
    else:
        novo = ValorModelo(modelo=modelo, valor_unitario=valor)
        db.add(novo)

    db.commit()
    valores = db.query(ValorModelo).order_by(ValorModelo.modelo.asc()).all()
    db.close()

    return templates.TemplateResponse("valores_modelos.html", {
        "request": request,
        "valores": valores,
        "mensagem": f"Valor atualizado para o modelo <b>{modelo}</b>: R$ {valor:.2f}"
    })

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
async def lancar_page(request: Request):
    return templates.TemplateResponse("lancar.html", {"request": request})

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
async def cadastro_formulario_page(request: Request):
    db = SessionLocal()
    modelos = db.query(Formulario).order_by(Formulario.nome_modelo.asc()).all()
    db.close()
    return templates.TemplateResponse("cadastro_formulario.html", {
        "request": request,
        "modelos": modelos
    })


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

@app.post("/responder_ficha", response_class=HTMLResponse)
async def responder_ficha(request: Request,
                          token: str = Form(...),
                          operador: str = Form(...),
                          funcao: str = Form(...),
                          db: Session = Depends(get_db)):

    ficha = db.query(Ficha).filter(Ficha.token_qr== token).first()
    if not ficha:
        return templates.TemplateResponse("formulario_operador.html", {
            "request": request,
            "ficha": None
        })

    # pega o valor unitário do modelo
    valor_registro = db.query(ValorModelo).filter(ValorModelo.modelo == ficha.modelo).first()
    valor_unitario = valor_registro.valor_unitario if valor_registro else 0

    # cria o registro de produção
    nova_producao = Producao(
        ficha_id=ficha.id,
        operador=operador,
        modelo=ficha.modelo,
        servico=funcao,
        tamanho="",
        quantidade=ficha.quantidade_total,
        valor=ficha.quantidade_total * valor_unitario
    )

    db.add(nova_producao)
    db.commit()

    return templates.TemplateResponse("pagina.html", {
        "request": request,
        "titulo": "Produção Registrada ✅",
        "mensagem": f"Ficha {ficha.numero_ficha} lançada com sucesso para <b>{operador}</b>!"
    })
# ========= FORMULÁRIO ABERTO PELO QR (GET exibe; POST grava) =========
@app.get("/responder_ficha", name="responder_ficha_qr", response_class=HTMLResponse)
async def responder_ficha_qr_get(request: Request, token: str):
    db = SessionLocal()
    ficha = db.query(Ficha).filter(Ficha.token_qr== token).first()
    db.close()

    if not ficha:
        # token inválido/expirado
        return templates.TemplateResponse(
            "pagina.html",
            {"request": request, "titulo": "QR inválido", "mensagem": "Ficha não encontrada ou QR expirado."},
        )

    # monta o form com dados da ficha
    return templates.TemplateResponse(
        "form_qr.html",
        {
            "request": request,
            "token": token,
            "numero_ficha": ficha.numero_ficha,
            "modelo": ficha.modelo,
            "funcao_padrao": ficha.funcao,
        },
    )


@app.post("/responder_ficha", response_class=HTMLResponse)
async def responder_ficha_qr_post(
    request: Request,
    token: str = Form(...),
    operador: str = Form(...),
    funcao: str = Form(...),
    modelo: str = Form(...),
    quantidade: int = Form(...)
):
    db = SessionLocal()

    ficha = db.query(Ficha).filter(Ficha.token_qr == token).first()
    if not ficha:
        db.close()
        return templates.TemplateResponse(
            "pagina.html",
            {"request": request, "titulo": "Erro", "mensagem": "QR inválido ou ficha não encontrada."},
        )

    # calcula valor pelo tabela valores_modelos (se existir)
    vm = db.query(ValorModelo).filter(ValorModelo.modelo == modelo).first()
    valor_unit = float(vm.valor_unitario) if vm else 0.0
    valor_total = valor_unit * quantidade

    lanc = Producao(
        ficha_id=ficha.id,
        usuario_id=None,              # se quiser, você pode buscar id do usuário operacional
        operador=operador,
        modelo=modelo,
        servico=funcao,
        tamanho=None,
        quantidade=quantidade,
        valor=valor_total,
        criado_em=datetime.utcnow(),
    )
    db.add(lanc)

    # opcional: se quiser “consumir” o QR para impedir reenvio, descomente:
    # ficha.token = None
    # ficha.status = StatusFicha.FINALIZADA

    db.commit()
    db.close()

    return templates.TemplateResponse(
        "pagina.html",
        {
            "request": request,
            "titulo": "Lançamento registrado ✅",
            "mensagem": (
                f"Ficha <b>{ficha.numero_ficha}</b> – Modelo <b>{modelo}</b><br>"
                f"Operador: <b>{operador}</b> | Função: <b>{funcao}</b><br>"
                f"Quantidade: <b>{quantidade}</b><br>"
                f"Valor total: <b>R$ {valor_total:,.2f}</b>"
            ),
        },
    )

    # Gera número da ficha (última +1)
    ultimo = db.query(Ficha).order_by(Ficha.id.desc()).first()
    numero_ficha = (int(ultimo.numero_ficha) + 1) if ultimo else 1000

    nova_ficha = Ficha(
        numero_ficha=str(numero_ficha),
        modelo=modelo,
        funcao=funcao,
        quantidade_total=quantidade,
        setor_atual=funcao,
    )

    db.add(nova_ficha)
    db.commit()

    # Gera QR code
    qr_data = f"Ficha {numero_ficha} - {modelo} - {funcao}"
    qr_img = qrcode.make(qr_data)
    buf = io.BytesIO()
    qr_img.save(buf, format="PNG")
    qr_code_base64 = base64.b64encode(buf.getvalue()).decode("utf-8")

    return templates.TemplateResponse("formulario_operador.html", {
        "request": request,
        "operador": operador,
        "funcao": funcao,
        "qr_code": qr_code_base64,
        "numero_ficha": numero_ficha
    })

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
    operador: str = Form(""),
    data_inicial: str = Form(""),
    data_final: str = Form("")
):
    db = SessionLocal()

    query = db.query(
        Producao.modelo,
        func.sum(Producao.quantidade).label("total_pecas"),
        func.sum(Producao.valor).label("total_valor")
    )

    if operador:
        query = query.filter(Producao.operador.ilike(f"%{operador}%"))
    if data_inicial:
        query = query.filter(Producao.criado_em >= data_inicial)
    if data_final:
        query = query.filter(Producao.criado_em <= data_final)

    query = query.group_by(Producao.modelo).order_by(func.sum(Producao.quantidade).desc())

    resultados = query.all()

    db.close()

    data = {
        "modelos": [r.modelo for r in resultados],
        "quantidades": [int(r.total_pecas or 0) for r in resultados],
        "valores": [float(r.total_valor or 0) for r in resultados],
    }

    return JSONResponse(content=data)

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

@app.get("/gerar_fichas", response_class=HTMLResponse)
async def gerar_fichas_page(request: Request):
    db = SessionLocal()
    modelos = db.query(Formulario).filter(Formulario.ativo == True).all()
    db.close()
    return templates.TemplateResponse("gerar_fichas.html", {
        "request": request,
        "modelos": modelos
    })


@app.post("/gerar_fichas")
async def gerar_fichas(request: Request, modelo: str = Form(...), qtd_fichas: int = Form(...)):
    db = SessionLocal()

    # pega a última ficha
    ultima_ficha = db.query(Ficha).order_by(Ficha.id.desc()).first()
    proximo_numero = 8000 if not ultima_ficha else int(ultima_ficha.numero_ficha) + 1

    # define quantidade padrão por tipo
    quantidade = 50 if "LUVA" in modelo.upper() else 20

    fichas = []

    # gera e salva no banco
    for i in range(qtd_fichas):
        token = str(uuid.uuid4())
        nova = Ficha(
            numero_ficha=str(proximo_numero + i),
            modelo=modelo,
            funcao="GERAL",           # ✅ valor padrão, evita NULL
            quantidade_total=quantidade,
            setor_atual="CORTE",      # opcional, ou defina outro setor inicial
            token=token
        )
        db.add(nova)
        fichas.append(nova)

    db.commit()

    # === Geração do PDF ===
    pdf_path = "fichas_geradas.pdf"
    c = canvas.Canvas(pdf_path, pagesize=A4)

    for ficha in fichas:
        qr_url = f"http://127.0.0.1:8000/responder_ficha?token={ficha.token}"
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
    db.close()

    return FileResponse(pdf_path, filename="fichas_geradas.pdf", media_type="application/pdf")
   
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
async def responder_ficha_page(request: Request, token: str):
    db = SessionLocal()
    ficha = db.query(Ficha).filter(Ficha.token_qr== token).first()
    db.close()
    if not ficha:
        return HTMLResponse("<h3>Ficha não encontrada ou QR inválido.</h3>", status_code=404)

    operador_logado = request.session.get("operador") or request.session.get("usuario")
    return templates.TemplateResponse("responder_ficha_operador.html", {
        "request": request,
        "numero_ficha": ficha.numero_ficha,
        "modelo": ficha.modelo,
        "quantidade": ficha.quantidade_total,
        "operador": operador_logado or "",
        "funcoes": FUNCOES_OPCOES,
        "token": token
    })

@app.post("/responder_ficha", response_class=HTMLResponse)
async def responder_ficha_submit(
    request: Request,
    token: str = Form(...),
    operador: str = Form(...),
    funcao: str = Form(...),
):
    db = SessionLocal()
    ficha = db.query(Ficha).filter(Ficha.token_qr== token).first()

    if not ficha:
        db.close()
        return HTMLResponse("<h3>Ficha não encontrada.</h3>", status_code=404)

    # grava a produção
    nova_producao = Producao(
        ficha_id=ficha.id,
        operador=operador,
        modelo=ficha.modelo,
        servico=funcao,
        tamanho=None,
        quantidade=ficha.quantidade_total,
        valor=0.0  # se quiser, calculamos depois com tabela de valores
    )

    db.add(nova_producao)
    db.commit()
    db.close()

    return templates.TemplateResponse("pagina.html", {
        "request": request,
        "titulo": "Produção lançada ✅",
        "mensagem": f"Ficha {ficha.numero_ficha} lançada para {operador} ({funcao}) – {ficha.quantidade_total} peças do modelo {ficha.modelo}."
    })

@app.get("/cadastrar_modelos", response_class=HTMLResponse)
async def cadastrar_modelos_page(request: Request):
    return templates.TemplateResponse("cadastrar_modelos.html", {"request": request})

@app.post("/cadastrar_modelo", response_class=HTMLResponse)
async def cadastrar_modelo(request: Request, modelo: str = Form(...), valor: float = Form(...)):
    db = SessionLocal()
    existente = db.query(ValorModelo).filter(ValorModelo.modelo == modelo).first()
    if existente:
        existente.valor_unitario = valor
    else:
        db.add(ValorModelo(modelo=modelo, valor_unitario=valor))
    db.commit()
    db.close()
    return templates.TemplateResponse("cadastrar_modelos.html", {
        "request": request,
        "mensagem": f"Modelo <b>{modelo}</b> salvo com sucesso (R$ {valor:.2f})."
    })

