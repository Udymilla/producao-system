from fastapi import FastAPI, Depends, HTTPException
from sqlalchemy.orm import Session
from database import SessionLocal, engine, Base
from models import Producao
from schemas import ProducaoCreate, ProducaoResponse
from typing import List

# Cria as tabelas se ainda não existirem
Base.metadata.create_all(bind=engine)

app = FastAPI(title="Sistema de Produção Dadalto")

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

# ✅ Rota para lançar produções
@app.post("/lancar", response_model=ProducaoResponse)
def lancar_producao(dados: ProducaoCreate, db: Session = Depends(get_db)):
    nova_ficha = Producao(**dados.dict())
    db.add(nova_ficha)
    db.commit()
    db.refresh(nova_ficha)
    return nova_ficha

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


