from fastapi import FastAPI, Depends, HTTPException, Query
from fastapi import Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from backend.database import SessionLocal, engine, Base
from backend.models import Producao, Ficha
from backend.schemas import ProducaoCreate, ProducaoResponse
from typing import List

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

# Rota de login (GET e POST)
@app.get("/login", response_class=HTMLResponse)
def login_page(request: Request):
    return templates.TemplateResponse("login.html", {"request": request})

@app.post("/login", response_class=HTMLResponse)
def login_action(request: Request, username: str = Form(...), password: str = Form(...)):
    # Simples autenticação estática (só pra testar)
    if username == "producao" and password == "1234":
        return RedirectResponse(url="/dashboard", status_code=303)
    elif username == "lider" and password == "4321":
        return RedirectResponse(url="/dashboard", status_code=303)
    else:
        return templates.TemplateResponse("login.html", {"request": request, "erro": "Usuário ou senha incorretos"})

@app.get("/dashboard", response_class=HTMLResponse)
def dashboard(request: Request):
    return templates.TemplateResponse("dashboard.html", {"request": request})
templates = Jinja2Templates(directory="backend/frontend/templates")

# Simulação inicial (sem banco ainda)
USUARIOS_FAKE = {
    "rafael": {"senha": "1234", "perfil": "lider"},
    "suelen": {"senha": "1234", "perfil": "producao"},
}

@app.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    return templates.TemplateResponse("login.html", {"request": request, "erro": False})

@app.post("/login", response_class=HTMLResponse)
async def login(request: Request, usuario: str = Form(...), senha: str = Form(...)):
    user = USUARIOS_FAKE.get(usuario.lower())
    if user and user["senha"] == senha:
        response = RedirectResponse(url=f"/dashboard?user={usuario}&perfil={user['perfil']}", status_code=303)
        return response
    return templates.TemplateResponse("login.html", {"request": request, "erro": True})

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

# ===== Página de Lançamento de Produção =====
@app.get("/lancar", response_class=HTMLResponse)
async def lancar_page(request: Request):
    return templates.TemplateResponse("pagina.html", {
        "request": request,
        "titulo": "Lançar Produção"
    })
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
    quantidade = form.get("quantidade")

    # Aqui futuramente faremos o INSERT no banco (por enquanto só exibe)
    return templates.TemplateResponse("pagina.html", {
        "request": request,
        "titulo": "Lançamento Concluído",
        "mensagem": f"Ficha lançada para {operador} - {modelo} ({quantidade} peças)"
    })
