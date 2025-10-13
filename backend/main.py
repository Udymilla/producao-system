from fastapi import FastAPI, Depends, HTTPException, Query
from fastapi import Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from backend.database import SessionLocal, engine, Base
from backend.models import Producao, Ficha, Usuario, UsuarioOperacional
from backend.schemas import ProducaoCreate, ProducaoResponse
from typing import List
import qrcode
import io
import base64

# Cria as tabelas se ainda não existirem
Base.metadata.create_all(bind=engine)


app = FastAPI(title="Sistema de Produção Dadalto")

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

@app.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    return templates.TemplateResponse("login.html", {"request": request, "erro": False})

@app.post("/login", response_class=HTMLResponse)
async def login_post(request: Request, usuario: str = Form(...), senha: str = Form(...)):
    db = SessionLocal()
    user = db.query(Usuario).filter_by(nome=usuario, senha=senha).first()
    db.close()

    if not user:
        return templates.TemplateResponse(
            "login.html",
            {"request": request, "erro": True}
        )

    # Redireciona conforme perfil do usuário
    if user.perfil.lower() == "administrador":
        return RedirectResponse(url="/administracao", status_code=303)
    else:
        return RedirectResponse(
            url=f"/dashboard?user={user.nome}&perfil={user.perfil}",
            status_code=303
            )

@app.get("/logout")
async def logout():
    return RedirectResponse(url="/login")

@app.get("/dashboard", response_class=HTMLResponse)
async def dashboard(request: Request, user: str = "", perfil: str = ""):
    return templates.TemplateResponse("dashboard.html", {
        "request": request,
        "usuario": user.capitalize(),
        "perfil": perfil.capitalize()
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

# Página de consulta de fichas
@app.get("/consultar_fichas", response_class=HTMLResponse)
async def consultar_fichas(request: Request):
    return templates.TemplateResponse("consultar_fichas.html", {"request": request})

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

    return RedirectResponse(url="/formulario_operador", status_code=302)
@app.get("/formulario_operador", response_class=HTMLResponse)
async def formulario_operador_page(request: Request):
    # Simulação temporária do operador logado
    operador = "Luana"
    funcao = "ACABAMENTO"
    return templates.TemplateResponse("formulario_operador.html", {"request": request, "operador": operador, "funcao": funcao})


@app.post("/formulario_operador", response_class=HTMLResponse)
async def formulario_operador_post(request: Request):
    form = await request.form()
    operador = form.get("operador")
    funcao = form.get("funcao")
    modelo = form.get("modelo")
    quantidade = int(form.get("quantidade"))

    db = SessionLocal()

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
