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

# ===== Página de cadastro de formulários (GET) =====
@app.get("/cadastro_formulario", response_class=HTMLResponse)
async def cadastro_formulario_page(request: Request):
    return templates.TemplateResponse("cadastro_formulario.html", {"request": request})

# ===== Receber dados do formulário (POST) =====
@app.post("/cadastro_formulario", response_class=HTMLResponse)
async def cadastro_formulario_post(request: Request):
    form = await request.form()
    modelo = form.get("modelo")
    cor = form.get("cor") or "Não informada"
    tamanhos = form.getlist("tamanhos")
    link = form.get("link")

    mensagem = (
        f"<b>Modelo:</b> {modelo}<br>"
        f"<b>Cor:</b> {cor}<br>"
        f"<b>Tamanhos:</b> {', '.join(tamanhos) if tamanhos else 'Nenhum selecionado'}<br>"
        f"<b>Link:</b> <a href='{link}' target='_blank' class='text-blue-600 underline'>{link}</a>"
    )

    return templates.TemplateResponse("pagina.html", {
        "request": request,
        "titulo": "Formulário Cadastrado com Sucesso ✅",
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

    # ========= GERAR FICHA + QR (usado por líder/admin na tela do operador) =========
@app.get("/formulario_operador", response_class=HTMLResponse)
async def formulario_operador_page(request: Request):
    # tela simples só para gerar a ficha e o QR (pode personalizar depois)
    return templates.TemplateResponse("formulario_operador.html", {"request": request})

@app.post("/formulario_operador", response_class=HTMLResponse)
async def formulario_operador_post(request: Request):
    form = await request.form()
    operador = (form.get("operador") or "").strip()
    funcao = (form.get("funcao") or "").strip()
    modelo = (form.get("modelo") or "").strip()
    quantidade_total = int(form.get("quantidade") or 0)

    db = SessionLocal()

    # número sequencial da ficha (F0001, F0002…)
    ultima = db.query(Ficha).order_by(Ficha.id.desc()).first()
    if not ultima:
        numero_ficha = "F0001"
    else:
        numero_ficha = f"F{int(ultima.numero_ficha[1:]) + 1:04d}"

    # token único para o QR
    token = secrets.token_urlsafe(16)

    nova_ficha = Ficha(
        numero_ficha=numero_ficha,
        modelo=modelo,
        funcao=funcao,
        quantidade_total=quantidade_total,
        setor_atual=funcao,
        token_qr=token,                   # <<< guarda o token para validar
        status=StatusFicha.EM_PRODUCAO,
    )
    db.add(nova_ficha)
    db.commit()
    db.refresh(nova_ficha)

    # link que o QR vai abrir no celular do operador
    url_form = request.url_for("responder_ficha_qr") + f"?token={token}"

    # gera QR (PNG em base64 para exibir na página)
    img = qrcode.make(url_form)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    qr_b64 = base64.b64encode(buf.getvalue()).decode("utf-8")

    db.close()

    return templates.TemplateResponse(
        "formulario_operador.html",
        {
            "request": request,
            "operador": operador,
            "funcao": funcao,
            "numero_ficha": numero_ficha,
            "modelo": modelo,
            "url_form": url_form,
            "qr_code": qr_b64,
        },
    )


# ========= FORMULÁRIO ABERTO PELO QR (GET exibe; POST grava) =========
@app.get("/responder_ficha", name="responder_ficha_qr", response_class=HTMLResponse)
async def responder_ficha_qr_get(request: Request, token: str):
    db = SessionLocal()
    ficha = db.query(Ficha).filter(Ficha.token_qr == token).first()
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
    # ficha.token_qr = None
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
